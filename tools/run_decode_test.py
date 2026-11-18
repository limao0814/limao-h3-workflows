# -*- coding: utf-8 -*-
"""狸猫AV latent解码驱动：LimaoH3AVLatentLoad → AVDecode → CreateVideo → SaveVideo"""
import json, urllib.request, sys, time

BASE = "http://127.0.0.1:8188"
LATENT_PATH = sys.argv[sys.argv.index("--latent") + 1] if "--latent" in sys.argv \
    else "limao_av_latent/huowu_shot1_av.safetensors"
PREFIX = sys.argv[sys.argv.index("--prefix") + 1] if "--prefix" in sys.argv \
    else "huowu/shot1_32g_test"

prompt = {
    "1": {"class_type": "LimaoH3AVLatentLoad", "inputs": {"path": LATENT_PATH}},
    "2": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "4": {"class_type": "MiniMaxH3AVDecodeT8", "inputs": {
        "av_latent": ["1", 0], "video_vae": ["2", 0], "audio_vae": ["3", 0]}},
    "5": {"class_type": "CreateVideo", "inputs": {
        "images": ["4", 0], "fps": 24, "audio": ["4", 1],
        "bit_depth": 8, "color_space": "sRGB", "chroma_subsampling": "none"}},
    "6": {"class_type": "SaveVideo", "inputs": {
        "video": ["5", 0], "filename_prefix": PREFIX, "format": "auto"}},
}
data = json.dumps({"prompt": prompt, "client_id": "limao-decode"}).encode()
req = urllib.request.Request(BASE + "/prompt", data=data, headers={"Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req, timeout=60))
except urllib.error.HTTPError as e:
    print("提交失败", e.code, e.read().decode()[:600]); sys.exit(1)
pid = r["prompt_id"]
print("解码提交:", pid)

t0 = time.time()
while time.time() - t0 < 1800:
    time.sleep(10)
    h = json.load(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=60))
    if pid not in h:
        print(f"  [{int(time.time()-t0)}s] 解码中…"); continue
    st = h[pid].get("status", {})
    if st.get("status_str") == "error":
        for m in st.get("messages", []):
            if m[0] == "execution_error":
                print("出错:", m[1]["node_type"], m[1]["exception_message"][:400])
        sys.exit(2)
    files = [img for o in h[pid].get("outputs", {}).values()
             for img in o.get("images", []) + o.get("gifs", []) + o.get("videos", [])]
    if files:
        el = int(time.time() - t0)
        print(f"✅ 解码完成 {el}s")
        for f in files:
            print("   产出:", f.get("filename"), f.get("subfolder"), f.get("type"))
        sys.exit(0)
    if st.get("completed"):
        print("完成但无文件, outputs:", json.dumps(h[pid].get("outputs", {}), ensure_ascii=False, default=str)[:500])
        sys.exit(3)
print("超时"); sys.exit(4)
