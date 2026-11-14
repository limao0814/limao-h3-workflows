# A/B 画质对照：从零版 vs 原版 DEBUG，同素材同种子
# 用法: python3 ab_run.py limao|origin
import json, urllib.request, sys, urllib.error
BASE = "http://127.0.0.1:6006"
SEED = 28022535127564
# 原版素材（按 89,88,87,86,37,6,35,36,90 顺序）
ORIG_IMGS = ["35481498a507d8e5f3c982dd59ad1db27031c0653a7cb828383c72130d824949.jpg",
             "507afdf6b2b62203e5fc42e356aa41e5.jpg",
             "b05320fc45bc32561ee6916b2dfc2a608be73f82f7aab2f4e96d07270ccf9bbe.jpg",
             "e6a44331bece137f967e3fe129fd043575830d1ca3a34c7ac306888ad019081a.jpg",
             "TIFA.jpg","beach.jpg","005.jpg","1.png","123.png"]
ORIG_AUDS = ["1.mp3","2.mp3","1.mp3"]

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)

oi = get("/object_info")
which = sys.argv[1] if len(sys.argv) > 1 else "limao"
WF = ("/root/ComfyUI/user/default/workflows/狸猫·H3视频/狸猫·H3·全域参考锻造·从零版.json"
      if which == "limao" else
      "/root/ComfyUI/user/default/workflows/狸猫·H3视频/狸猫·DEBUG·原版双采对照.json")
wf = json.load(open(WF))
nodes = {n["id"]: n for n in wf["nodes"]}
links = {l[0]: l for l in wf.get("links", [])}

PRIM = {"STRING", "INT", "FLOAT", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3"}

def widget_types(cls):
    info = oi.get(cls)
    if not info:
        return []
    out = []
    for sec in ("required", "optional"):
        for name, spec in info["input"].get(sec, {}).items():
            if isinstance(spec, list) and spec:
                t = spec[0]
                if t == "COMFY_DYNAMICCOMBO_V3":
                    out.append((name, "dyn"))
                elif isinstance(t, list) or t in PRIM:
                    is_upload = isinstance(t, str) and "UPLOAD" in t
                    out.append((name, "prim" if not is_upload else "skip"))
                else:
                    out.append((name, "port"))
    return out

def is_upload_widget(cls, name):
    info = oi.get(cls)
    if not info:
        return False
    for sec in ("required", "optional"):
        spec = info["input"].get(sec, {}).get(name)
        if spec and isinstance(spec, list) and spec and isinstance(spec[0], str) and "UPLOAD" in spec[0]:
            return True
    return False

def norm_combo(cls, name, val):
    if not isinstance(val, str):
        return val
    info = oi.get(cls)
    if not info:
        return val
    for sec in ("required", "optional"):
        spec = info["input"].get(sec, {}).get(name)
        if spec and isinstance(spec, list) and isinstance(spec[0], list):
            opts = spec[0]
            if val in opts:
                return val
            for o in opts:
                if isinstance(o, str) and (o.startswith(val) or val.startswith(o) or o.split(" — ")[0] == val):
                    return o
    return val

# widget 显示值 → API 值映射
COMBO_MAP = {"Ref2VA — 参考生音视频": "Ref2VA"}

def dyn_combo_specs(cls, name):
    """DYNAMICCOMBO: 返回 (所有option列表, 默认key)"""
    info = oi.get(cls)
    if not info:
        return [], None
    for sec in ("required", "optional"):
        spec = info["input"].get(sec, {}).get(name)
        if spec and isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], dict):
            opts = spec[1].get("options", [])
            return opts, spec[1].get("default")
    return [], None

prompt = {}
prompt_nodes = {}
client = "limao-ab" if which == "limao" else "origin-ab"

def resolve(nid, slot, depth=0):
    """递归解析 bypass(mode=4) 透传: 返回 (src_id_str, slot)"""
    n = nodes[nid]
    if n.get("mode") == 4 and depth < 10:
        for inp in n.get("inputs", []):
            if inp.get("link") is not None:
                lk = links[inp["link"]]
                return resolve(lk[1], lk[2], depth + 1)
        return None
    return (str(nid), slot)

# 素材计数器（仅 limao 版替换）
img_i = 0
aud_i = 0

for nid, n in nodes.items():
    mode = n.get("mode", 0)
    if mode != 0:
        continue
    cls = n["type"]
    if cls not in oi:
        continue
    inputs = {}
    link_names = set()
    for inp in n.get("inputs", []):
        if inp.get("link") is not None:
            lk = links[inp["link"]]
            r = resolve(lk[1], lk[2])
            if r is None:
                continue
            inputs[inp["name"]] = [r[0], r[1]]
            link_names.add(inp["name"])

    wv = n.get("widgets_values", [])
    if isinstance(wv, dict):
        for k, v in wv.items():
            if k not in inputs and v is not None:
                inputs[k] = COMBO_MAP.get(v, norm_combo(cls, k, v))
    else:
        wi = 0
        for name, kind in widget_types(cls):
            if kind == "port":
                continue
            if wi >= len(wv):
                break
            val = wv[wi]; wi += 1
            if name in link_names:
                continue
            if name in inputs or val is None:
                continue
            if kind == "dyn":
                # selection 值本身也要赋给 API input
                inputs[name] = COMBO_MAP.get(val, norm_combo(cls, name, val))
                # 所选 option 的动态子参数依序消费后续 widgets，API 命名 name.sub
                opts, _def = dyn_combo_specs(cls, name)
                for o in opts:
                    if o.get("key") != val:
                        continue
                    for sub_name in (o.get("inputs", {}).get("required", {}) or {}):
                        if wi >= len(wv):
                            break
                        sv = wv[wi]; wi += 1
                        pref = name + "." + sub_name
                        if pref in link_names or pref in inputs:
                            continue
                        if sv is not None:
                            inputs[pref] = sv
                continue
            if is_upload_widget(cls, name):
                continue
            inputs[name] = COMBO_MAP.get(val, norm_combo(cls, name, val))

    # ---- A/B 特殊处理 ----
    if cls == "RandomNoise":
        inputs["noise_seed"] = SEED
        inputs["control"] = "fixed"
    prompt[str(nid)] = {"class_type": cls, "inputs": inputs}
    if cls == "LoadImage" or cls == "LoadAudio" or cls == "LoadVideo":
        prompt_nodes[str(nid)] = cls

# 替换素材（两版同一套，保证 A/B 公平）：9 图 / 3 音频
if True:
    img_ids = sorted([k for k, v in prompt_nodes.items() if v == "LoadImage"])
    aud_ids = sorted([k for k, v in prompt_nodes.items() if v == "LoadAudio"])
    for i, k in enumerate(img_ids[:9]):
        prompt[k]["inputs"]["image"] = ORIG_IMGS[i % len(ORIG_IMGS)]
    for i, k in enumerate(aud_ids[:3]):
        prompt[k]["inputs"]["audio"] = ORIG_AUDS[i % len(ORIG_AUDS)]
    print("素材替换: %d 图 %d 音频" % (min(len(img_ids),9), min(len(aud_ids),3)))


# origin 特判：旧 UI json 的 widgets 顺序与新 schema 错位，直接钉当年验证过的正确值
if which == "origin":
    for k, v in prompt.items():
        if v["class_type"] == "BlockSparseAttention":
            for kk in ("selection", "selection.tau", "start_percent", "end_percent", "dense_blocks",
                       "min_tokens", "extra_tokens", "sink_conditioning", "verbose"):
                if kk in v["inputs"]:
                    del v["inputs"][kk]
            v["inputs"].update({"selection": "sol-attn", "selection.tau": 1.3, "start_percent": 0.2,
                                "end_percent": 0.9, "dense_blocks": "", "min_tokens": 12288,
                                "extra_tokens": 256, "sink_conditioning": "exact_kv_and_rows", "verbose": False})
        if v["class_type"] == "CreateVideo" and v["inputs"].get("chroma_subsampling") == "none":
            v["inputs"]["chroma_subsampling"] = "auto"

# origin 版旧文件名映射：基模/LoRA 子目录前缀 + 缺失素材替换
if which == "origin":
    FIX_FILE = {"ff21598437b423882c4db4b55aa6c1a212f12e00fa013cbf9d9d392e60773db0.png": "155d443821b50fddaecd10b51bb495f1.jpg",
                "24c14631a1afdf8499c532415b17327a04f6c2590e27ad54746ad40174cc5401.png": "35481498a507d8e5f3c982dd59ad1db27031c0653a7cb828383c72130d824949.jpg",
                "3d8a39572158ab1ac22e22804551caf3c9b2517a14cc648ef04decb2a185d524.mp3": "1.mp3"}
    for k, v in prompt.items():
        ins = v["inputs"]
        for fk, fv in FIX_FILE.items():
            for kk in ("image", "audio"):
                if ins.get(kk) == fk:
                    ins[kk] = fv
        for kk in ("unet_name", "lora_name"):
            val = ins.get(kk)
            if isinstance(val, str):
                info = oi.get(v["class_type"])
                opts = None
                for sec in ("required", "optional"):
                    spec = info["input"].get(sec, {}).get(kk) if info else None
                    if spec and isinstance(spec, list) and isinstance(spec[0], list):
                        opts = spec[0]
                if opts is not None and val not in opts:
                    if "minimax/" + val in opts:
                        ins[kk] = "minimax/" + val
                    else:
                        cand = [o for o in opts if val.split("_curveproj")[0] in o or o.endswith(val)]
                        if cand:
                            ins[kk] = cand[0]
                        else:
                            print("WARN 未匹配", kk, val)

data = json.dumps({"prompt": {k: {"class_type": v["class_type"], "inputs": v["inputs"]} for k, v in prompt.items()},
                   "client_id": client}).encode()
req = urllib.request.Request(BASE + "/prompt", data=data, headers={"Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req, timeout=30))
    print(which, "提交成功 prompt_id:", r.get("prompt_id"))
except urllib.error.HTTPError as e:
    print(which, "提交失败", e.code)
    print(e.read().decode()[:3000])
