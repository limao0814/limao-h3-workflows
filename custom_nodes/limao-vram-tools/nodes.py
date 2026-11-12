# -*- coding: utf-8 -*-
"""limao-vram-tools · 狸猫AI 显存优化节点包
LimaoVAEChunkDecode: 视频VAE按帧分块解码（防长序列/高分辨率一次性解码爆显存）
LimaoVRAMGuard:      采样段间主动清空显存缓存（等价 BanZhang VRAM_Guard/Cleaner）
版权: 狸猫AI LIMAO-H3-20261112, 禁止移除本声明或二次分发
"""
import torch

class LimaoVRAMGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "anything": ("*", {"tooltip": "直通输入（模型/latent/图像均可）"}),
                "aggressive": ("BOOLEAN", {"default": True}),
            },
            "hidden": {},
        }
    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("passthrough",)
    FUNCTION = "run"
    CATEGORY = "limao/显存优化"

    def run(self, anything, aggressive):
        try:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                if aggressive:
                    try:
                        torch.cuda.ipc_collect()
                    except Exception:
                        pass
                try:
                    import gc
                    for _ in range(2):
                        gc.collect()
                except Exception:
                    pass
        except Exception:
            pass
        return (anything,)

class LimaoVAEChunkDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_latent": ("LATENT",),
                "video_vae": ("VAE",),
                "chunk_frames": ("INT", {"default": 32, "min": 4, "max": 160, "step": 4,
                                          "tooltip": "每次解码的帧数，越小越省显存（32 适配 24G，24/16 适配更低显存）"}),
                "dtype_mode": (["auto", "fp32", "fp16", "bfloat16"], {"default": "auto"}),
                "empty_cache_between_chunks": ("BOOLEAN", {"default": True}),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("frames",)
    FUNCTION = "decode"
    CATEGORY = "limao/显存优化"

    def _to_image_bhwc(self, out):
        # 统一转换 VAE.decode 输出 → ComfyUI IMAGE [N,H,W,C]
        if out.dim() == 5:
            if out.shape[1] == 3:   # [B,C,T,H,W]（通道在前，MiniMax H3）→ [B*T,H,W,C]
                b, c, t, h, w = out.shape
                out = out.permute(0, 2, 3, 4, 1).reshape(b * t, h, w, c)
            else:                   # [B,T,C,H,W] → [B*T,H,W,C]
                b, t, c, h, w = out.shape
                out = out.permute(0, 1, 3, 4, 2).reshape(b * t, h, w, c)
        elif out.dim() == 4:    # [B,C,H,W] → [B,H,W,C]
            out = out.permute(0, 2, 3, 1)
        return out

    def decode(self, video_latent, video_vae, chunk_frames, dtype_mode, empty_cache_between_chunks):
        samples = video_latent["samples"]
        meta = {k: v for k, v in video_latent.items() if k != "samples"}
        n = samples.dim()
        if n == 5:
            if samples.shape[2] > samples.shape[1]:
                # [B,C,T,H,W] 通道在前（MiniMax H3 视频 latent）
                b, c, t, h, w = samples.shape
                dim_t = 2
            else:
                # [B,T,C,H,W] 时间在前
                b, t, c, h, w = samples.shape
                dim_t = 2
        elif n == 4:
            b, c, h, w = samples.shape
            t, dim_t = 1, None
        else:
            raise ValueError(f"[limao] 不支持的 latent 维度: {samples.shape}")

        results = []
        vae_dtype = None
        try:
            vae_dtype = video_vae.first_stage_model.dtype
        except Exception:
            pass
        want_dtype = None
        if dtype_mode != "auto":
            want_dtype = {"fp32": torch.float32, "fp16": torch.float16,
                          "bfloat16": torch.bfloat16}[dtype_mode]
        target_dtype = want_dtype or vae_dtype

        def decode_chunk(chunk):
            out = video_vae.decode(chunk)
            try:
                import json as _json, os as _os
                _log = _os.path.join(_os.path.expanduser('~'), 'limao-decode-shapes.log')
                open(_log, 'a').write(_json.dumps({
                    'latent_shape': list(samples.shape), 'chunk_shape': list(chunk.shape),
                    'out_shape': list(out.shape) if hasattr(out, 'shape') else str(type(out)),
                    'meta_keys': sorted(meta.keys())}) + '\n')
            except Exception:
                pass
            if not torch.is_tensor(out):
                out = out[0]
            if target_dtype is not None and out.dim() >= 2:
                pass  # 输出转 float32 交给 ComfyUI 正常管线
            return out

        if dim_t is None or t <= chunk_frames:
            out = decode_chunk(samples)
            results.append(self._to_image_bhwc(out))
        else:
            for t0 in range(0, t, chunk_frames):
                t1 = min(t0 + chunk_frames, t)
                chunk = samples[:, :, t0:t1, :, :] if dim_t == 2 else samples[:, :, t0:t1, :, :]
                out = decode_chunk(chunk)
                results.append(self._to_image_bhwc(out))
                if empty_cache_between_chunks and torch.cuda.is_available():
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        pass
        image = torch.cat(results, dim=0)
        return (image.float(),)

class LimaoPeakWatch:
    """记录执行时显存峰值（诊断用，直通）"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "anything": ("*",),
            "reset_peak": ("BOOLEAN", {"default": True}),
        }}
    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("passthrough",)
    FUNCTION = "run"
    CATEGORY = "limao/显存优化"

    def run(self, anything, reset_peak):
        try:
            if torch.cuda.is_available():
                if reset_peak:
                    torch.cuda.reset_peak_memory_stats()
                used = torch.cuda.memory_allocated() / 1024**3
                peak = torch.cuda.max_memory_allocated() / 1024**3
                print(f"[limao] 显存: 已用 {used:.1f} GB / 峰值 {peak:.1f} GB / 总量 {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB")
        except Exception:
            pass
        return (anything,)

NODE_CLASS_MAPPINGS = {
    "LimaoVRAMGuard": LimaoVRAMGuard,
    "LimaoVAEChunkDecode": LimaoVAEChunkDecode,
    "LimaoPeakWatch": LimaoPeakWatch,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LimaoVRAMGuard": "狸猫·显存守护 VRAMGuard",
    "LimaoVAEChunkDecode": "狸猫·分块解码 ChunkDecode",
    "LimaoPeakWatch": "狸猫·显存峰值监控",
}
print("[limao-vram-tools] 狸猫AI 显存优化节点包已加载 (LIMAO-H3-20261112)")
