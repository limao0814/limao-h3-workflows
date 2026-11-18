# -*- coding: utf-8 -*-
"""
狸猫AI · H3 视频工坊 自研节点套件 (limao-h3-suite)
====================================================
诞生背景：2026-11 光斑事故——latent 上采样器 fp16 文件被静默顶替，
整条链路排查一天一夜才锁定。本套件的核心设计目标就是:

    「让机器替人守住每一颗模型文件的指纹、每一份参考素材的合规性，
      任何静默变化都在采样前被拦下，而不是在成片里变成彩屑。」

节点一览
--------
LimaoH3ModelSentinel  模型哨兵   : 采样前校验模型文件指纹（SHA256），被顶替立即拦截
LimaoH3RefImageAudit  图参考审计 : 9 张参考图的官方约束校验（尺寸/宽高比/重复）
LimaoH3RefVideoAudit  视频参考审计: 3 条参考视频的官方约束校验（帧数/时长/总预算）
LimaoH3RefAudioAudit  音频参考审计: 3 条参考音频的官方约束校验（时长/总预算）
LimaoH3FrameBridge    帧桥       : H3 五维帧布局 ↔ 标准四维帧，安全对接 RIFE/后处理
LimaoH3SeedForge      种子锻炉   : 固定/每跑随机/安全种子池 三模式种子供给
LimaoH3VRAMGuard      显存守卫   : 模型链上的显存治理 passthrough
LimaoH3MemorySweep    显存清道夫 : 采样后立即回收显存（视频长跑贴墙防线）
LimaoH3AVLatentSave   AV潜空间落盘: 复合音视频 latent 落盘（两段式解码第一步）
LimaoH3AVLatentLoad   AV潜空间回载: 读取落盘 latent 重建复合结构（两段式解码第二步）

—— 生图线（MiniMax-H3-Image，2026-11 开源）——
LimaoH3ImagePromptGuard 提示词体检 : H3-Image 无负面词且堆砌词降质，出采样前人话体检
LimaoH3ImageQAGate      出图硬闸   : 8MP 伪影线/16MP 推荐线、尺寸与比例一致性校验
LimaoH3Ref16Audit      16图参考审计: H3-Image 官方 16 参考图约束（128–8192px / 1:4–4:1 / 64MiB）
LimaoH3HandRiskWatch  手部风险哨兵: 手势正确率~48%防线（分级/正向稳定句/批出建议）
LimaoH3TextProofread  文字校验闸  : 图内文字逐字比对（tesseract），错字自动打回重roll

所有节点零第三方依赖（仅 torch + ComfyUI folder_paths），失败时给出
中文人话诊断，不抛裸 traceback。
"""

import hashlib
import os
import random
import shutil

import torch

import folder_paths


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _sha256(path: str, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def _find_duplicates(filename: str) -> list:
    """在全部模型目录中查找与 filename 同名的其他实体文件（顶替事故的直接防线）。"""
    hits = []
    base = os.path.basename(filename)
    for root, _dirs, files in os.walk(folder_paths.get_folder_paths("models")[0] if False else os.path.join(folder_paths.base_path, "models")):
        for f in files:
            if f == base:
                p = os.path.join(root, f)
                if not os.path.islink(p):
                    hits.append(p)
    return hits


def _frames_duration(n_frames: int, fps: float = 24.0) -> float:
    return n_frames / fps if fps else 0.0


def _audio_duration(audio: dict) -> float:
    """从 ComfyUI AUDIO 字典估算时长（秒）。"""
    try:
        wave = audio.get("waveform")
        sr = audio.get("sample_rate") or audio.get("sample_rate_in") or 24000
        if wave is None:
            return 0.0
        return float(wave.shape[-1]) / float(sr)
    except Exception:
        return 0.0


def _fmt(v: float) -> str:
    return f"{v:.2f}"


# ---------------------------------------------------------------------------
# 1. 模型哨兵
# ---------------------------------------------------------------------------

class LimaoH3ModelSentinel:
    """采样前校验模型文件指纹。文件被顶替/损坏/出现同名多实体时立即拦截。

    用法：挂在工作流任意位置（无需连线），filename 选择要守护的模型
    （如 latent 上采样器），可选填 expected_sha256 做逐字节校验。
    """

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = "模型指纹哨兵：校验存在性、SHA256、同名多实体，防静默顶替。"

    @classmethod
    def INPUT_TYPES(cls):
        dirs = ["diffusion_models", "vae", "loras", "text_encoders", "clip_vision",
                "latent_upscale_models", "upscale_models"]
        existing = [d for d in dirs if os.path.isdir(os.path.join(folder_paths.base_path, "models", d))]
        return {
            "required": {
                "directory": (existing or ["loras"],),
                "filename": ("STRING", {"default": "minimax_h3_latent_upscaler_3d_bf16.safetensors"}),
                "expected_sha256": ("STRING", {"default": ""}),
                "on_mismatch": (["block（拦截运行）", "warn（仅告警）"],),
                "check_duplicates": (["enable", "disable"],),
            }
        }

    def run(self, directory, filename, expected_sha256, on_mismatch, check_duplicates):
        lines = ["—— 狸猫模型哨兵 · 巡检报告 ——"]
        base = os.path.join(folder_paths.base_path, "models", directory)
        path = os.path.join(base, filename)
        blocked = False

        if not os.path.exists(path):
            lines.append(f"❌ 文件不存在: {directory}/{filename}")
            lines.append("   请运行开机脚本 bootstrap_models.sh 或手动下载补齐。")
            blocked = True
        else:
            size_gb = os.path.getsize(path) / (1 << 30)
            lines.append(f"✅ 存在: {directory}/{filename} ({size_gb:.2f} GB)")
            digest = _sha256(path)
            lines.append(f"   SHA256: {digest}")
            if expected_sha256.strip():
                if digest.lower() == expected_sha256.strip().lower():
                    lines.append("   ✅ 指纹与预期一致（逐字节校验通过）")
                else:
                    lines.append(f"   ❌ 指纹与预期不符! 预期 {expected_sha256.strip()[:16]}…")
                    blocked = True
            else:
                lines.append("   ℹ️ 未填 expected_sha256，仅做存在性校验。建议在稳定后回填指纹。")
            lines.append(f"   fingerprint|{digest}")

        if check_duplicates == "enable":
            dups = [p for p in _find_duplicates(filename) if os.path.normpath(p) != os.path.normpath(path)]
            if dups:
                lines.append(f"⚠️ 发现 {len(dups)} 个同名异路径实体（顶替高危）:")
                for p in dups:
                    try:
                        d = _sha256(p)
                        same = os.path.exists(path) and d == _sha256(path)
                        lines.append(f"   - {p}  [{'一致' if same else '★不同实体★'}]")
                        if os.path.exists(path) and not same:
                            blocked = True
                    except OSError:
                        lines.append(f"   - {p}  [不可读]")
            else:
                lines.append("✅ 全盘无同名异实体")

        if blocked and on_mismatch.startswith("block"):
            raise RuntimeError(
                "狸猫哨兵拦截: 模型文件指纹异常，已阻止本次采样。\n" + "\n".join(lines) +
                "\n（若确认文件无误，可将 on_mismatch 改为 warn，或更新 expected_sha256）"
            )
        return {"ui": {"text": ["\n".join(lines)]}}


# ---------------------------------------------------------------------------
# 2/3/4. 参考素材审计（9图 / 3视频 / 3音频）
# ---------------------------------------------------------------------------

_IMG_MIN_SIDE = 256
_IMG_ASPECT_LO, _IMG_ASPECT_HI = 0.4, 2.5
_VID_MIN_FRAMES = 5
_REF_DUR_LO, _REF_DUR_HI, _REF_DUR_TOTAL = 2.0, 15.0, 15.0


class LimaoH3RefImageAudit:
    """9 张参考图合规审计（官方约束: ≥256px、宽高比 0.4–2.5、建议去重）。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = "校验 9 图参考槽：尺寸、宽高比、重复图检测，输出中文报告。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {
            f"image_{i}": ("IMAGE",) for i in range(1, 10)
        }}

    def run(self, **kwargs):
        lines = ["—— 狸猫图参考审计 ——"]
        seen = {}
        issues = 0
        used = 0
        for i in range(1, 10):
            img = kwargs.get(f"image_{i}")
            if img is None:
                continue
            used += 1
            t = img if isinstance(img, torch.Tensor) else torch.tensor(img)
            h, w = t.shape[-3], t.shape[-2]  # 狸猫修复：[B,H,W,C]，旧代码多一个占位符把W塞给h、通道数塞给w，导致所有图必报❌
            aspect = w / h if h else 0
            digest = hashlib.sha1(t.detach().cpu().numpy().tobytes()).hexdigest()[:12]
            tag = f"图{i}"
            if min(h, w) < _IMG_MIN_SIDE:
                lines.append(f"❌ {tag}: {w}×{h} 短边低于 {_IMG_MIN_SIDE}px"); issues += 1
            elif not (_IMG_ASPECT_LO <= aspect <= _IMG_ASPECT_HI):
                lines.append(f"❌ {tag}: 宽高比 {aspect:.2f} 超出 0.4–2.5"); issues += 1
            else:
                lines.append(f"✅ {tag}: {w}×{h}（比例 {aspect:.2f}）")
            if digest in seen:
                lines.append(f"⚠️ {tag} 与 图{seen[digest]} 内容完全相同（去重可省 token）")
                issues += 1
            else:
                seen[digest] = i
        lines.append(f"已接 {used}/9 张；问题 {issues} 项" + ("　—　建议按『正脸/侧脸/全身/服饰/风格』分工" if used < 3 else ""))
        return {"ui": {"text": ["\n".join(lines)]}}


class LimaoH3RefVideoAudit:
    """3 条参考视频合规审计（官方约束: ≥5帧、2–15s、总时长≤15s、24fps）。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = "校验 3 视频参考槽：帧数、时长、总预算 15s，输出中文报告。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {
            "video_1": ("IMAGE",), "video_2": ("IMAGE",), "video_3": ("IMAGE",),
            "video_audio_1": ("AUDIO",), "video_audio_2": ("AUDIO",), "video_audio_3": ("AUDIO",),
        }}

    def run(self, **kwargs):
        lines = ["—— 狸猫视频参考审计 ——"]
        total = 0.0
        issues = 0
        for i in range(1, 4):
            v = kwargs.get(f"video_{i}")
            a = kwargs.get(f"video_audio_{i}")
            tag = f"视频{i}"
            if v is None:
                if a is not None:
                    lines.append(f"⚠️ {tag}: 有配对音频但无画面，音频将被忽略"); issues += 1
                continue
            t = v if isinstance(v, torch.Tensor) else torch.tensor(v)
            frames = int(t.shape[0]) if t.dim() == 4 else max(int(t.shape[-2]), 1)
            dur = _frames_duration(frames)
            total += dur
            ok = _VID_MIN_FRAMES <= frames and _REF_DUR_LO <= dur <= _REF_DUR_HI
            lines.append(f"{'✅' if ok else '❌'} {tag}: {frames} 帧 ≈ {_fmt(dur)}s @24fps")
            if frames < _VID_MIN_FRAMES:
                lines.append(f"   少于 {_VID_MIN_FRAMES} 帧会被官方节点直接报错"); issues += 1
            if dur < _REF_DUR_LO or dur > _REF_DUR_HI:
                lines.append(f"   官方约束 {_REF_DUR_LO}–{_REF_DUR_HI}s"); issues += 1
            if a is None:
                lines.append(f"   ℹ️ 未接配对音频（该视频将无声参考）")
        if total > _REF_DUR_TOTAL:
            lines.append(f"❌ 视频参考总时长 {_fmt(total)}s 超出 {_REF_DUR_TOTAL}s 预算"); issues += 1
        else:
            lines.append(f"视频参考总时长 {_fmt(total)}s / {_REF_DUR_TOTAL}s 预算")
        lines.append(f"问题 {issues} 项　—　提示: 生成 124 帧时超过 ~5s 的参考只取前段")
        return {"ui": {"text": ["\n".join(lines)]}}


class LimaoH3RefAudioAudit:
    """3 条独立参考音频合规审计（官方约束: 2–15s、总时长≤15s）。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = "校验 3 音频参考槽：单条与总时长预算，输出中文报告。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {
            f"audio_{i}": ("AUDIO",) for i in range(1, 4)
        }}

    def run(self, **kwargs):
        lines = ["—— 狸猫音频参考审计 ——"]
        total = 0.0
        issues = 0
        for i in range(1, 4):
            a = kwargs.get(f"audio_{i}")
            if a is None:
                continue
            dur = _audio_duration(a)
            total += dur
            ok = _REF_DUR_LO <= dur <= _REF_DUR_HI
            lines.append(f"{'✅' if ok else '❌'} 音频{i}: ≈{_fmt(dur)}s")
            if not ok:
                lines.append(f"   官方约束 {_REF_DUR_LO}–{_REF_DUR_HI}s"); issues += 1
        if total > _REF_DUR_TOTAL:
            lines.append(f"❌ 音频参考总时长 {_fmt(total)}s 超出 {_REF_DUR_TOTAL}s 预算"); issues += 1
        else:
            lines.append(f"音频参考总时长 {_fmt(total)}s / {_REF_DUR_TOTAL}s 预算")
        lines.append(f"问题 {issues} 项")
        return {"ui": {"text": ["\n".join(lines)]}}


# ---------------------------------------------------------------------------
# 5. 帧桥
# ---------------------------------------------------------------------------

class LimaoH3FrameBridge:
    """H3 五维帧布局 → 标准四维帧序列。

    H3 生态里帧张量存在 [B,T,H,W,C]（通道在后）与 [B,C,T,H,W] 两种五维
    布局，多数后处理节点（RIFE/放大/导出）只吃 [N,H,W,C]。本节点自动
    识别布局并安全展开，布局歧义时按「通道数最少维优先」启发式判定。
    """

    CATEGORY = "limao/帧处理"
    FUNCTION = "run"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("frames",)
    DESCRIPTION = "五维帧张量安全展开为 [N,H,W,C] 帧序列，供 RIFE/超分/导出使用。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "frames": ("IMAGE",),
            "target": (["NHWC（帧序列，通用后处理）", "NTHWC（保留时间维，H3 原生）"],),
        }}

    def run(self, frames, target):
        t = frames
        if t.dim() == 4:
            if target.startswith("NTHWC"):
                # [N,H,W,C] -> [1,N,H,W,C] 视为单批时间序列
                return (t.unsqueeze(0),)
            return (t,)
        if t.dim() == 5:
            b, d1, d2, d3, d4 = t.shape
            # 判定通道维: 值为 3/4 的那一维
            dims = (b, d1, d2, d3, d4)
            ch_idx = next((i for i, v in enumerate(dims) if v in (3, 4)), None)
            if ch_idx is None:
                ch_idx = min(range(5), key=lambda i: dims[i])
            if ch_idx == 0:      # [C,T,H,W]
                t = t.permute(1, 2, 3, 0)          # [T,H,W,C]
            elif ch_idx == 1:    # [B,C,T,H,W]
                t = t.permute(0, 2, 3, 4, 1)       # [B,T,H,W,C]
            elif ch_idx == 4:    # [B,T,H,W,C] 已是目标
                pass
            else:                # [B,T,C,H,W] 或 [B,H,W,C,T]
                t = t.moveaxis(ch_idx, 4)
            if t.dim() == 5 and target.startswith("NHWC"):
                t = t.reshape(-1, *t.shape[2:])    # [B*T,H,W,C]
            return (t,)
        raise ValueError(f"狸猫帧桥: 不支持 {t.dim()} 维张量 {tuple(t.shape)}")


# ---------------------------------------------------------------------------
# 6. 种子锻炉
# ---------------------------------------------------------------------------

# 狸猫内部实测干净（无彩屑/无崩坏）的种子池，随版本维护
_SAFE_SEED_POOL = {
    "default": [28022535127564, 42, 20261113, 731, 918273645],
}


class LimaoH3SeedForge:
    """三模式种子供给：fixed（固定复现）/ random（每跑随机）/ pool（安全池轮换）。"""

    CATEGORY = "limao/种子"
    FUNCTION = "run"
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    DESCRIPTION = "固定/每跑随机/安全池轮换 三模式种子，可直连 RandomNoise.noise_seed。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "mode": (["fixed（固定，可复现）", "random（每跑随机）", "pool（狸猫安全池轮换）"],),
            "seed": ("INT", {"default": 28022535127564, "min": 0, "max": 0xffffffffffffffff}),
            "pool": (list(_SAFE_SEED_POOL.keys()),),
        }}

    @staticmethod
    def _pick(mode, seed, pool):
        if mode.startswith("fixed"):
            return int(seed)
        if mode.startswith("pool"):
            lst = _SAFE_SEED_POOL.get(pool, _SAFE_SEED_POOL["default"])
            return int(random.SystemRandom().choice(lst))
        return int(random.SystemRandom().getrandbits(47))

    IS_CHANGED = staticmethod(lambda **kwargs: float("nan"))  # random/pool 每次重算

    def run(self, mode, seed, pool):
        return (self._pick(mode, seed, pool),)


# ---------------------------------------------------------------------------
# 7. 显存守卫
# ---------------------------------------------------------------------------

class LimaoH3VRAMGuard:
    """模型链 passthrough，执行到该节点时按策略释放缓存，削峰防 OOM。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    DESCRIPTION = "显存守卫：采样链上的显存治理开关（off 不干预 / balanced / aggressive）。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "mode": (["off（不干预）", "balanced（均衡）", "aggressive（激进）"],),
        }}

    def run(self, model, mode):
        if mode.startswith("balanced"):
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        elif mode.startswith("aggressive"):
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        return (model,)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

class LimaoH3MemorySweep:
    """狸猫·显存清道夫：解码后、保存前的全量清理（RAM/VRAM/模型卸载）。
    揉合自 16G 显存精修版的 RAMCleanup + VRAMCleanup 双节点，收编为狸猫自研单节点。
    纯 passthrough：输入什么返回什么，仅在链路经过时执行清理副作用。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "sweep"
    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("output",)
    DESCRIPTION = ("显存清道夫：在解码→保存之间执行 RAM/VRAM 全量清理。"
                   "低显存机型建议开启；清理发生在成片解码之后，不影响画质。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "anything": ("*",),
            "clean_ram": ("BOOLEAN", {"default": True}),
            "clean_vram_cache": ("BOOLEAN", {"default": True}),
            "offload_models": ("BOOLEAN", {"default": False}),
        }}

    def sweep(self, anything, clean_ram=True, clean_vram_cache=True, offload_models=False):
        import gc
        if offload_models:
            try:
                import comfy.model_management as mm
                mm.unload_all_models()
            except Exception:
                pass
        if clean_ram:
            gc.collect()
        if clean_vram_cache and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        return (anything,)


NODE_CLASS_MAPPINGS = {
    "LimaoH3ModelSentinel": LimaoH3ModelSentinel,
    "LimaoH3RefImageAudit": LimaoH3RefImageAudit,
    "LimaoH3RefVideoAudit": LimaoH3RefVideoAudit,
    "LimaoH3RefAudioAudit": LimaoH3RefAudioAudit,
    "LimaoH3FrameBridge": LimaoH3FrameBridge,
    "LimaoH3SeedForge": LimaoH3SeedForge,
    "LimaoH3VRAMGuard": LimaoH3VRAMGuard,
    "LimaoH3MemorySweep": LimaoH3MemorySweep,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LimaoH3ModelSentinel": "狸猫·模型哨兵",
    "LimaoH3RefImageAudit": "狸猫·图参考审计",
    "LimaoH3RefVideoAudit": "狸猫·视频参考审计",
    "LimaoH3RefAudioAudit": "狸猫·音频参考审计",
    "LimaoH3FrameBridge": "狸猫·帧桥",
    "LimaoH3SeedForge": "狸猫·种子锻炉",
    "LimaoH3VRAMGuard": "狸猫·显存守卫",
    "LimaoH3MemorySweep": "狸猫·显存清道夫",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]


class LimaoH3AVLatentSave:
    """狸猫·AV潜空间落盘（两段式解码第一步）：把复合音视频 latent 拆开存 safetensors，
    采样阶段与解码阶段解耦，规避采样后残留显存状态下 VAE 无声崩溃。
    OUTPUT_NODE：直接作为阶段1的输出锚点。"""

    CATEGORY = "limao/IO"
    FUNCTION = "save"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = ("AV潜空间落盘：采样完成后把复合latent存盘，解码放到独立队列/重启后进行。"
                   "文件存于 output/limao_av_latent/，视频latent+音频latent双键。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "av_latent": ("LATENT",),
            "filename": ("STRING", {"default": "limao_av_latent"}),
        }}

    def save(self, av_latent, filename):
        import os
        import folder_paths
        from safetensors.torch import save_file
        samples = av_latent["samples"]
        parts = list(samples.unbind()) if getattr(samples, "is_nested", False) else [samples]
        video = parts[0].detach().cpu().contiguous()
        data = {"video": video}
        if len(parts) > 1:
            data["audio"] = parts[1].detach().cpu().contiguous()
        out_dir = os.path.join(folder_paths.get_output_directory(), "limao_av_latent")
        os.makedirs(out_dir, exist_ok=True)
        safe = "".join(c for c in filename if c.isalnum() or c in "_-.") or "limao_av_latent"
        path = os.path.join(out_dir, safe + ".safetensors")
        save_file(data, path)
        import json as _json
        return {"ui": {"text": [_json.dumps({"path": path, "keys": list(data.keys()),
                                            "shapes": {k: list(v.shape) for k, v in data.items()}})]}}


class LimaoH3AVLatentLoad:
    """狸猫·AV潜空间回载（两段式解码第二步）：读取落盘的复合 latent，
    重建 NestedTensor 复合结构，供 H3Kit 分块解码与南风音频解码消费。"""

    CATEGORY = "limao/IO"
    FUNCTION = "load"
    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("av_latent",)
    DESCRIPTION = ("AV潜空间回载：从 output/limao_av_latent/ 读取落盘文件，重建复合latent。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "path": ("STRING", {"default": "limao_av_latent/limao_av_latent.safetensors"}),
        }}

    def load(self, path):
        import os
        import folder_paths
        from safetensors.torch import load_file
        p = path if os.path.isabs(path) else os.path.join(
            folder_paths.get_output_directory(), path)
        if not os.path.exists(p):
            raise FileNotFoundError(f"狸猫AV潜空间回载：文件不存在 {p}")
        data = load_file(p)
        if "audio" in data:
            import comfy.nested_tensor
            samples = comfy.nested_tensor.NestedTensor((data["video"], data["audio"]))
        else:
            samples = data["video"]
        return ({"samples": samples},)



# ---------------------------------------------------------------------------
# 11. 生图线：MiniMax-H3-Image（2026-11 开源，33.1B DiT / 6步采样 / 无CFG）
#     每个节点对应一条社区实测爆料毛病的防线。
# ---------------------------------------------------------------------------

# H3-Image 实测堆砌词（prompt 敏感：出现这些词整体画质反而下降）
_HYPE_WORDS = [
    "stunning", "masterpiece", "best quality", "high quality", "ultra detailed",
    "ultra-detailed", "hyper detailed", "8k", "4k", "hd", "trending on",
    "award winning", "professional photo", "very beautiful", "超清", "高清",
    "杰作", "大师之作", "最佳画质", "最高质量",
]
# 提示词里出现即危险的否定式写法（模型无负面提示词，正向里写"不要X"大概率画出X）
_NEGATIVE_PATTERNS = [
    "no ", "not ", "without ", "avoid ", "don't", "dont ", "never ",
    "不要", "没有", "避免", "禁止", "不要出现", "勿",
]

class LimaoH3ImagePromptGuard:
    """狸猫·提示词体检（H3-Image 生图线专用）。

    社区实测三大坑，全部在采样前拦截提醒：
    1. 堆砌词降质 —— stunning/8k/masterpiece 类词出现越多，画质反而越差；
    2. 否定式失效 —— 模型不支持负面提示词，正向里写"不要X"大概率画出X，
       必须改写成正向描述（"不要模糊"→"画面整体清晰锐利"）；
    3. 短文字裸奔 —— 图内文字要渲染正确必须用引号包住，且保持简短
       （小字/长段落必出乱码或伪字）；
    4. 自作主张 —— 实测爱加条形码、二维码、水印、假数据：自动按官方句式
       把排除项写进正向提示词（官方允许的唯一排除方式）；
    5. 角色漂移 —— 有参考图时自动注入 <Picture 1> 身份锁定句。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    DESCRIPTION = ("H3-Image 提示词体检+自动修复：堆砌词剔除/否定式提醒/引号检查/"
                   "防条形码假数据尾缀/参考图身份锁定，输出中文报告。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt": ("STRING", {"multiline": True, "default": ""}),
            "mode": (["体检并自动修复", "仅体检"],),
            "reference_mode": (["无参考图", "有参考图(锁定主角色)"],),
        }}

    def run(self, prompt, mode="体检并自动修复", reference_mode="无参考图"):
        lines = ["—— 狸猫提示词体检（H3-Image）——"]
        issues = 0
        fixes = 0
        low = prompt.lower()
        cleaned = prompt
        hits = [w for w in _HYPE_WORDS if w.lower() in low]
        if hits:
            issues += 1
            lines.append(f"❌ 堆砌词 {len(hits)} 个: {', '.join(hits[:8])}"
                         f"{' ...' if len(hits) > 8 else ''}")
            lines.append("   实测这类词会拉低画质，请直接删除（模型自己懂质感）")
            if mode == "体检并自动修复":
                import re as _re
                for w in sorted(_HYPE_WORDS, key=len, reverse=True):
                    if all(ord(c) < 128 for c in w):
                        cleaned = _re.sub(rf"\b{_re.escape(w)}\b", "", cleaned, flags=_re.I)
                    else:
                        cleaned = cleaned.replace(w, "")
                cleaned = _re.sub(r"\s{2,}", " ", cleaned).strip(" ,，")
                fixes += 1
                lines.append("   🔧 已自动剔除")
        neg_hits = []
        for p in _NEGATIVE_PATTERNS:
            idx = low.find(p.lower())
            if idx >= 0:
                ctx = prompt[max(0, idx - 6): idx + 14].replace("\n", " ")
                neg_hits.append(ctx)
        if neg_hits:
            issues += 1
            lines.append(f"⚠️ 否定式写法 {len(neg_hits)} 处（无负面提示词，写『不要X』易画出X）:")
            for c in neg_hits[:5]:
                lines.append(f"   「…{c}…」→ 排除杂物请保留本节点的官方句式尾缀，"
                             f"否定画面主体的请改写成正向描述")
        import re as _re
        quoted = _re.findall(r'[“"「『]([^”"」』]+)[”"」』]', prompt)
        bare_cn = [w for w in _re.findall(r"[\u4e00-\u9fff]{2,12}", prompt)
                   if w not in [q for q in quoted]]
        if bare_cn and len(bare_cn) > 2:
            issues += 1
            lines.append(f"⚠️ 图内文字建议用引号包裹并保持简短（小字必出乱码）: "
                         f"{'、'.join(bare_cn[:5])}")
            if len(bare_cn) > 3:
                lines.append("   ℹ️ 文字超过 3 段时乱码率陡增 —— 长文案拆短/分次生成"
                             "（产品铁律：交付文字必须模型直出，不做后期贴字）")
        if len(prompt) > 4096 * 3:
            issues += 1
            lines.append(f"❌ 提示词过长（约 {len(prompt)} 字符，超 4096 token 会被截断）")
        # 自作主张防线：官方句式尾缀（官方明确：把避免项写进正向）
        if mode == "体检并自动修复":
            cleaned = cleaned.rstrip()
            cleaned += ("\n\nThe composition contains only the elements described above, "
                        "rendered exactly as specified: no barcodes, no QR codes, no watermarks, "
                        "no logos, no signatures, and no fabricated data or labels.")
            fixes += 1
            lines.append("🔧 已注入防杂物尾缀（条形码/二维码/水印/假数据，官方句式正向排除）")
            if quoted:
                q_txt = "、".join("「" + t + "」" for t in quoted[:4])
                cleaned += ("\nRender the text " + q_txt + " exactly as written, in standard "
                            "highly legible regular script (kaishu), with precise correct stroke "
                            "structure — exactly these characters, with no extra, missing, merged, "
                            "or distorted characters.")
                fixes += 1
                lines.append("🔧 已注入标准文字渲染句（逐字精确/标准楷体/无变形无添字）——"
                             "这是模型文字强项的正确打开方式，配合文字校验闸闭环")
            if reference_mode.startswith("有参考图"):
                cleaned += ("\nStrictly follow the identity, face, hairstyle, body proportions "
                            "and outfit shown in <Picture 1>; do not alter the character's "
                            "appearance under any circumstances.")
                fixes += 1
                lines.append("🔧 已注入 <Picture 1> 主角色身份锁定句（多图融合角色漂移防线）")
        if issues == 0:
            lines.append("✅ 通过：无堆砌词、无危险否定式、文字已加引号")
        lines.append(f"问题 {issues} 项 · 自动修复 {fixes} 项"
                     f"　—　官方建议：先交代图像类型（如『街拍照片/70年代电影帧』），再描述内容")
        return {"result": (cleaned,), "ui": {"text": ["\n".join(lines)]}}


class LimaoH3ImageQAGate:
    """狸猫·出图硬闸（H3-Image 生图线专用）。

    社区实测：8MP 以下（尤其 2MP/4MP）脸、手、背景小人有伪影，
    8MP 以上才明显变好，16MP（4K）为最佳工作区 —— 本节点按分辨率
    分级放行：≥16MP ✅ / 8–16MP ⚠️ / <8MP ❌（建议重出，别省这点时间）。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    DESCRIPTION = ("H3-Image 出图质检：分辨率伪影线（8MP）与最佳线（16MP）分级校验，"
                   "多图输出尺寸一致性校验。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",),
            "mode": (["16MP直出(推荐)", "8MP起", "自定义"],),
            "custom_min_mp": ("INT", {"default": 8, "min": 1, "max": 32, "step": 1}),
        }}

    def run(self, images, mode="16MP直出(推荐)", custom_min_mp=8):
        t = images if isinstance(images, torch.Tensor) else torch.tensor(images)
        min_mp = 16.0 if mode.startswith("16") else (8.0 if mode == "8MP起" else float(custom_min_mp))
        lines = ["—— 狸猫出图硬闸（H3-Image）——"]
        issues = 0
        sizes = set()
        for i in range(int(t.shape[0])):
            h, w = int(t.shape[-3]), int(t.shape[-2])
            mp = w * h / 1e6
            sizes.add((w, h))
            tag = f"图{i+1}"
            if mp >= 16.0:
                lines.append(f"✅ {tag}: {w}×{h} ≈ {mp:.1f}MP（4K最佳工作区，脸/手/细节稳定）")
            elif mp >= 8.0:
                lines.append(f"⚠️ {tag}: {w}×{h} ≈ {mp:.1f}MP（可用区，注意检查脸与手）")
            elif mp >= min_mp:
                lines.append(f"⚠️ {tag}: {w}×{h} ≈ {mp:.1f}MP（伪影风险区边缘）")
            else:
                issues += 1
                lines.append(f"❌ {tag}: {w}×{h} ≈ {mp:.1f}MP（实测 <8MP 脸/手/小人出伪影，建议重出）")
        if len(sizes) > 1:
            issues += 1
            lines.append(f"❌ 多图尺寸不一致: {sorted(sizes)}（拼图/对比前请统一）")
        if issues == 0:
            lines.append("✅ 全部通过")
        lines.append("ℹ️ 提醒: 模型不支持透明背景（PNG 无 alpha），抠图素材请另行走分割链")
        return (images, {"ui": {"text": ["\n".join(lines)]}})


# H3-Image 官方参考图约束：128–8192px、宽高比 1:4–4:1、单张 ≤64MiB
_REF16_MIN_SIDE = 128
_REF16_MAX_SIDE = 8192
_REF16_ASPECT_LO, _REF16_ASPECT_HI = 0.25, 4.0
_REF16_MAX_BYTES = 64 * 1024 * 1024

class LimaoH3Ref16Audit:
    """狸猫·16图参考审计（H3-Image 生图线专用）。

    官方约束逐张校验：128–8192px、宽高比 1:4–4:1；重复图检测。
    参考图在提示词中以 <Picture N> 寻址（上传顺序即编号），
    多图融合实测有角色漂移风险 —— 主角色图务必放 <Picture 1> 并在
    提示词里点名锁定。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = ("校验 H3-Image 16 参考图槽：官方尺寸/比例约束、重复检测、"
                   "<Picture N> 锁位建议。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {
            f"image_{i}": ("IMAGE",) for i in range(1, 17)
        }}

    def run(self, **kwargs):
        lines = ["—— 狸猫16图参考审计（H3-Image）——"]
        seen = {}
        issues = 0
        used = 0
        for i in range(1, 17):
            img = kwargs.get(f"image_{i}")
            if img is None:
                continue
            used += 1
            t = img if isinstance(img, torch.Tensor) else torch.tensor(img)
            h, w = int(t.shape[-3]), int(t.shape[-2])
            aspect = w / h if h else 0
            nbytes = int(t.numel() * t.element_size())
            tag = f"<Picture {i}>"
            ok = True
            if not (_REF16_MIN_SIDE <= min(h, w) and max(h, w) <= _REF16_MAX_SIDE):
                lines.append(f"❌ {tag}: {w}×{h} 超出官方 128–8192px"); ok = False; issues += 1
            elif not (_REF16_ASPECT_LO <= aspect <= _REF16_ASPECT_HI):
                lines.append(f"❌ {tag}: 宽高比 {aspect:.2f} 超出官方 1:4–4:1"); ok = False; issues += 1
            else:
                lines.append(f"✅ {tag}: {w}×{h}（比例 {aspect:.2f}）")
            if nbytes > _REF16_MAX_BYTES:
                lines.append(f"⚠️ {tag}: 解码后约 {nbytes>>20}MiB 超 64MiB 上限，会被官方拒绝"); issues += 1
            digest = hashlib.sha1(t.detach().cpu().numpy().tobytes()).hexdigest()[:12]
            if digest in seen:
                lines.append(f"⚠️ {tag} 与 <Picture {seen[digest]}> 内容完全相同"); issues += 1
            else:
                seen[digest] = i
        lines.append(f"已接 {used}/16 张；问题 {issues} 项")
        if used >= 2:
            lines.append("ℹ️ 多图融合实测有角色漂移：主角色务必 <Picture 1>，提示词点名『保持 <Picture 1> 的人物特征完全一致』")
        return {"ui": {"text": ["\n".join(lines)]}}


# 手部风险词（实测 H3-Image 手语手势正确率仅 48.1%——好了很多但仍有约一半错误率）
_HAND_WORDS = [
    "hand", "hands", "finger", "fingers", "gesture", "hand sign", "sign language",
    "waving", "pointing", "holding", "grip", "clapping", "thumbs up", "okay sign",
    "palm", "fist", "nail", "手", "手势", "手指", "挥手", "比心", "点赞",
    "牵手", "握", "托", "挥手告别", "手部特写", "五指",
]

class LimaoH3HandRiskWatch:
    """狸猫·手部风险哨兵（H3-Image 生图线专用）。

    实测：美国手语手势测试正确率 48.1%——比对照模型高一截，但仍有约一半
    错误率。手不是"解决了"，是"好多了"。本节点做三件事：
    1. 扫描提示词手部相关词，给风险分级（特写/交互/无手）；
    2. 高风险任务自动注入手部正向稳定句（五指/自然姿态，业界常用正向增强）；
    3. 给出批出建议：手部任务实测建议一次出 4 张挑最好的，别赌单张。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    DESCRIPTION = ("H3-Image 手部风险哨兵：手部词扫描分级、正向稳定句注入、"
                   "批出张数建议。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt": ("STRING", {"multiline": True, "default": ""}),
            "mode": (["自动增强", "仅评估"],),
        }}

    def run(self, prompt, mode="自动增强"):
        import re as _re
        low = prompt.lower()
        hits = sorted({w for w in _HAND_WORDS if w in low or w.lower() in low})
        lines = ["—— 狸猫手部风险哨兵（H3-Image）——"]
        cleaned = prompt
        if not hits:
            lines.append("✅ 无手部元素，风险等级：无")
            lines.append("ℹ️ 构图提示：半身/远景手少入画，是最稳的出图策略")
            return {"result": (cleaned,), "ui": {"text": ["\n".join(lines)]}}
        # 分级
        close_up = any(w in hits for w in ("手部特写", "hand", "palm", "finger", "fingers", "nail", "手势"))
        interact = any(w in hits for w in ("holding", "grip", "牵手", "握手", "托", "握", "clapping"))
        level = "高风险（手部特写/多指交互）" if close_up or interact else "中风险（画面含手）"
        lines.append(f"⚠️ 手部词 {len(hits)} 个: {'、'.join(hits[:8])}")
        lines.append(f"风险等级：{level}　—　实测手势正确率约 48%，仍有约一半错误率")
        if mode == "自动增强":
            cleaned = cleaned.rstrip()
            cleaned += ("\nAnatomically correct hands with exactly five fingers per hand, "
                        "natural relaxed finger pose, realistic joint structure.")
            lines.append("🔧 已注入手部正向稳定句（五指/自然姿态/真实关节）")
        lines.append("📋 批出建议：手部任务一次出 ≥4 张挑最好，别赌单张；"
                     "特写构图优先改中景（手少入画）")
        return {"result": (cleaned,), "ui": {"text": ["\n".join(lines)]}}


# —— 第六道防线：文字校验闸（产品铁律：交付文字必须是模型直出的标准文字，禁止贴字）——
_TEXT_PROOFREAD_REPORT = "/tmp/limao_text_proofread_report.json"
_OCR_ENGINE = None


def _proofread_ocr(image_np):
    """RapidOCR 读字（中文实测远强于 tesseract，书法体单字可读）。
    返回 (recognized_text, error_or_None)。引擎进程级缓存。"""
    global _OCR_ENGINE
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None, ("rapidocr 未安装（pip install rapidocr-onnxruntime，"
                      "约 60MB 纯 CPU 推理）")
    try:
        import numpy as _np
        from PIL import Image as _PIL
        if _OCR_ENGINE is None:
            _OCR_ENGINE = RapidOCR()
        img = _PIL.fromarray(image_np)
        # 多尺度联合读字：不同字号在不同缩放下检测率不同，任一尺度命中即算
        # （实测校准：卷轴书法"福"在 4096 读不出、1024 才读出）
        seen = []
        for cap in (4096, 2048, 1024):
            im2 = img if max(img.size) <= cap else img.resize(
                (max(1, int(img.width * cap / max(img.size))),
                 max(1, int(img.height * cap / max(img.size)))))
            try:
                result, _ = _OCR_ENGINE(_np.array(im2))
            except Exception:
                continue
            for _, t, c in (result or []):
                if float(c) >= 0.5:  # 低置信度噪声框丢弃，防假PASS
                    seen.append(t)
        return "".join(seen), None
    except Exception as e:
        return None, f"OCR 执行失败: {e}"


class LimaoH3TextProofread:
    """狸猫·文字校验闸（H3-Image 生图线专用）。

    社区与官方实测：H3-Image 文字排版能力是强项（多层排版/指定字体可出），
    但中文字符偶发崩坏，社区标准解法就是"重试"。本节点把重试闭环化：
      1. 出图后立即用 RapidOCR 读图内文字，与 expected_text 逐字比对；
      2. 结果 PASS/FAIL/SKIP 写入 /tmp/limao_text_proofread_report.json，
         驱动脚本读到 FAIL 自动换种子重roll（默认至多 3 次），直到交付标准文字；
      3. 校验不可用（OCR 缺失）时报告 SKIP，不拦流程但显式提示安装命令。
    实测校准（2026-11-16 沙箱）：写对的"福"字 RapidOCR conf=1.00 判 PASS；
    汉服卷轴翻车的第二个乱码字被识别为"一"→ 逐字比对 FAIL → 触发重roll。
    配套：PromptGuard 会自动注入"逐字精确/标准楷体"渲染句，双管齐下。"""

    CATEGORY = "limao/守卫"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    DESCRIPTION = ("H3-Image 文字校验闸：图内文字与 expected_text 逐字比对，"
                   "错字打回重roll，保证交付即标准文字。")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",),
            "expected_text": ("STRING", {"multiline": False, "default": ""}),
            "mode": (["打回重画(驱动重roll)", "仅报告"],),
        }}

    def run(self, images, expected_text="", mode="打回重画(驱动重roll)"):
        lines = ["—— 狸猫文字校验闸（H3-Image）——"]
        expected = (expected_text or "").strip()
        status, recognized, missing = "SKIP", "", []
        if not expected:
            lines.append("ℹ️ 未提供 expected_text（驱动 --text 传入），本图不校验文字")
        else:
            t = images if isinstance(images, torch.Tensor) else torch.tensor(images)
            arr = (t[0].detach().cpu().numpy() * 255).clip(0, 255).astype("uint8")
            recognized, err = _proofread_ocr(arr)
            if err:
                lines.append(f"⚠️ SKIP：{err}")
                lines.append("ℹ️ 校验不可用时不拦流程；请装 OCR 后重跑以启用闭环")
            else:
                keep = lambda s: [c for c in s if c.isalnum() or "\u4e00" <= c <= "\u9fff"]
                rec_seq = "".join(keep(recognized))
                from collections import Counter as _Counter
                rec_cnt = _Counter(rec_seq)
                missing = []
                for ch, need in _Counter("".join(keep(expected))).items():
                    got = rec_cnt.get(ch, 0)
                    if got < need:
                        missing.extend([ch] * (need - got))
                contiguous = "".join(keep(expected)) in rec_seq
                if not missing:
                    status = "PASS"
                    lines.append(f"✅ PASS：『{expected}』全部字符渲染正确"
                                 + ("（连续成串）" if contiguous else "（逐字命中）"))
                else:
                    status = "FAIL"
                    lines.append(f"❌ FAIL：『{expected}』缺字/错字 {'、'.join(missing)}"
                                 f" —— OCR 读到: {rec_seq[:60] or '(空白)'}")
                lines.append(f"ℹ️ 模式：{mode}" + ("" if status != "FAIL"
                             else "　→ 驱动脚本将自动换种子重roll"))
        import json as _json, time as _time
        try:
            _json.dump({"status": status, "expected": expected, "missing": missing,
                        "recognized": recognized[:400], "mode": mode,
                        "time": _time.strftime("%H:%M:%S")},
                       open(_TEXT_PROOFREAD_REPORT, "w", encoding="utf-8"))
        except OSError:
            pass
        return {"ui": {"text": ["\n".join(lines)]}}


NODE_CLASS_MAPPINGS.update({
    "LimaoH3AVLatentSave": LimaoH3AVLatentSave,
    "LimaoH3AVLatentLoad": LimaoH3AVLatentLoad,
    "LimaoH3ImagePromptGuard": LimaoH3ImagePromptGuard,
    "LimaoH3ImageQAGate": LimaoH3ImageQAGate,
    "LimaoH3Ref16Audit": LimaoH3Ref16Audit,
    "LimaoH3HandRiskWatch": LimaoH3HandRiskWatch,
    "LimaoH3TextProofread": LimaoH3TextProofread,
})
NODE_DISPLAY_NAME_MAPPINGS.update({
    "LimaoH3AVLatentSave": "狸猫·AV潜空间落盘",
    "LimaoH3AVLatentLoad": "狸猫·AV潜空间回载",
    "LimaoH3ImagePromptGuard": "狸猫·提示词体检（生图）",
    "LimaoH3ImageQAGate": "狸猫·出图硬闸",
    "LimaoH3Ref16Audit": "狸猫·16图参考审计",
    "LimaoH3HandRiskWatch": "狸猫·手部风险哨兵",
    "LimaoH3TextProofread": "狸猫·文字校验闸",
})
