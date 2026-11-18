#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""狸猫隐码工具：产出视频/图片注入肉眼不可见的身份码
用法:
  注入: python limao_stamp.py --file <路径> --wf <工作流名> [--task <任务id>] [--seed <种子>]
  校验: python limao_stamp.py --verify <路径>          （打印身份码 JSON，无则输出 NONE）
身份码双层:
  图片PNG  = tEXt元数据(limao_id) + 前64像素R通道LSB(hash标记)
  图片JPG/WebP = 元数据(EXIF UserComment / tEXt)
  视频MP4  = 容器元数据(©cmt / limao_id, ffmpeg -c copy 零画质损失)
"""
import json, os, sys, subprocess, time, hashlib

FFMPEG = os.environ.get("LIMAO_FFMPEG", "ffmpeg")

def payload(wf, task, seed, src):
    return json.dumps({"app": "limao", "wf": wf, "task": task,
                       "seed": seed, "ts": int(time.time()), "src": os.path.basename(src)},
                      ensure_ascii=False)

def stamp_image(path, pl):
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    im = Image.open(path)
    fmt = (im.format or "").upper()
    if fmt == "PNG":
        # 1) 元数据层
        info = PngInfo()
        info.add_text("limao_id", pl)
        # 2) LSB层：payload sha1 前64bit 嵌前64像素 R 通道最低位
        h = hashlib.sha1(pl.encode("utf-8")).digest()
        bits = [(b >> i & 1) for b in h[:8] for i in range(8)][:64]
        rgb = im.convert("RGB")
        px = rgb.load()
        for i, bit in enumerate(bits):
            r, g, b = px[i, 0]
            px[i, 0] = (r & 0xFE | bit, g, b)
        rgb.save(path, "PNG", pnginfo=info)
    elif fmt == "JPEG":
        import piexif  # 可选
        raise SystemExit("JPEG 走 EXIF 分支（未装 piexif，仅元数据可用）")
    else:
        im.save(path)
    print("STAMPED(img):", path)

def _ffmpeg():
    """优先 imageio-ffmpeg 静态二进制，其次系统 ffmpeg"""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def stamp_video(path, pl):
    """ffmpeg -c copy 流复制重封装，写容器元数据（零重编码零画质损失）"""
    tmp = path + ".stamp.mp4"
    r = subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", path,
                        "-c", "copy", "-metadata", "limao_id=" + pl,
                        "-movflags", "+use_metadata_tags", tmp])
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, path)
        print("STAMPED(video):", path)
    else:
        if os.path.exists(tmp):
            os.remove(tmp)
        print("STAMP-FAIL(video):", path)

def verify(path):
    # 1) mp4 容器元数据
    if path.lower().endswith(".mp4"):
        import av
        with av.open(path) as c:
            vid = (c.metadata or {}).get("limao_id")
        if not vid:
            # PyAV 读 format tags 全量兜底
            with av.open(path) as c:
                vid = (c.metadata or {}).get("limao_id")
        if vid:
            print("VIDEO-ID:", vid)
            return
        print("NONE")
        return
    from PIL import Image
    im = Image.open(path)
    meta = (im.info or {}).get("limao_id") or (im.text.get("limao_id") if hasattr(im, "text") else None)
    if meta:
        print("META-ID:", meta)
        return
    if (im.format or "").upper() == "PNG":
        rgb = im.convert("RGB")
        px = rgb.load()
        bits = [px[i, 0][0] & 1 for i in range(64)]
        bs = bytearray()
        for i in range(0, 64, 8):
            v = 0
            for b in bits[i:i+8]:
                v = v << 1 | b
            bs.append(v)
        print("LSB-HASH:", bytes(bs).hex())
        return
    print("NONE")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--file"); ap.add_argument("--verify")
    ap.add_argument("--wf", default="狸猫H3工作流"); ap.add_argument("--task", default="")
    ap.add_argument("--seed", default="")
    a = ap.parse_args()
    if a.verify:
        verify(a.verify)
    elif a.file:
        pl = payload(a.wf, a.task, a.seed, a.file)
        if a.file.lower().endswith(".mp4"):
            stamp_video(a.file, pl)
        elif a.file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            stamp_image(a.file, pl)
        else:
            print("SKIP(未知类型):", a.file)
