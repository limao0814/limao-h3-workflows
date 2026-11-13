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

所有节点零第三方依赖（仅 torch + ComfyUI folder_paths），失败时给出
中文人话诊断，不抛裸 traceback。
"""

import hashlib
import os
import random

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
            _, h, w = t.shape[-3], t.shape[-2], t.shape[-1]
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
