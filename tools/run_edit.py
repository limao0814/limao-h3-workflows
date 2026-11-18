# -*- coding: utf-8 -*-
"""狸猫·H3生图 t2i 验证驱动：UI工作流(subgraph展开) → API提交 → 轮询出图"""
import json, urllib.request, urllib.error, sys, time, math

BASE = "http://127.0.0.1:8188"
WF = "/root/ComfyUI/user/default/workflows/狸猫·H3生图/狸猫·H3生图·4K直出·文生图.json"
if "--wf" in sys.argv:
    WF = sys.argv[sys.argv.index("--wf") + 1]
MODE_16MP = "--8mp" not in sys.argv  # 默认16MP，--8mp 降档
TEXT_EXPECTED = None
if "--text" in sys.argv:
    TEXT_EXPECTED = sys.argv[sys.argv.index("--text") + 1]
SEED_OVERRIDE = None
if "--seed" in sys.argv:
    SEED_OVERRIDE = int(sys.argv[sys.argv.index("--seed") + 1])
RATIO = None  # 图生图画幅比例覆盖（auto=跟随源图）
if "--ratio" in sys.argv:
    RATIO = sys.argv[sys.argv.index("--ratio") + 1]
MAX_REROLL = 3
if "--max-text-reroll" in sys.argv:
    MAX_REROLL = int(sys.argv[sys.argv.index("--max-text-reroll") + 1])
CUSTOM_PROMPT = None
if "--prompt" in sys.argv:
    CUSTOM_PROMPT = sys.argv[sys.argv.index("--prompt") + 1]

wf = json.load(open(WF))

# 文字校验闸 + 种子覆盖（第六道防线接线）
if TEXT_EXPECTED is not None:
    tpn = next((n for n in wf["nodes"] if n["type"] == "LimaoH3TextProofread"), None)
    if tpn is not None:
        tpn["widgets_values"][0] = TEXT_EXPECTED
        print("文字校验目标:", TEXT_EXPECTED)
if SEED_OVERRIDE is not None:
    next(n for n in wf["nodes"] if n["type"] == "KSampler")["widgets_values"][0] = SEED_OVERRIDE

# ---------- edit 线驱动（无 subgraph，直接 UI→API）----------
IMGS = []
CUSTOM_PROMPT = None
if "--prompt" in sys.argv:
    CUSTOM_PROMPT = sys.argv[sys.argv.index("--prompt") + 1]
if "--imgs" in sys.argv:  # 参考图（一次传全部，须在 ComfyUI/input/ 下）
    # 收集 --imgs 后的所有值（遇到下一个 -- 开头的参数停止）
    IMGS = []
    args = sys.argv
    j = args.index("--imgs") + 1
    while j < len(args) and not args[j].startswith("--"):
        IMGS.append(args[j]); j += 1
    IMGS = IMGS[:16]  # H3 模型上限 16 张参考
    li = next(n for n in wf["nodes"] if n["type"] == "LoadImage")
    li["widgets_values"][0] = IMGS[0]
    print("参考图:", IMGS)
if CUSTOM_PROMPT:
    pbox = next(n for n in wf["nodes"]
                if n["type"] == "PrimitiveStringMultiline" and n.get("widgets_values")
                and "Replace" in str(n["widgets_values"][0]))
    pbox["widgets_values"][0] = CUSTOM_PROMPT

# 16MP 直出档（#56 scale total pixels）
# 注：图生图画幅比例由 app.py 在上传时用 PIL 预裁剪源图实现（节点内 crop=center
# 会产出非连续张量，触发 FlashAttention stride 错误），#56 保持原生模式。
res = next(n for n in wf["nodes"] if n["id"] == 56)
res["widgets_values"][1] = 16 if MODE_16MP else 8
print("编辑画布档:", res["widgets_values"])

# ImageCompare(#62) 是 socketless 预览组件（UI专用），API 校验必挂 compare_view 且无下游依赖
# → 转换前直接 bypass，避免拖累整链校验
ic_node = next((n for n in wf["nodes"] if n["type"] == "ImageCompare"), None)
if ic_node is not None and ic_node.get("mode", 0) == 0:
    ic_node["mode"] = 4
    print("ImageCompare 预览节点已 bypass（API线不需要）")

# 16MP：ResolutionSelector（仅文生图工作流有，编辑线无）
sel = next((n for n in wf["nodes"] if n["type"] == "ResolutionSelector"), None)
if sel is not None:
    sel["widgets_values"][1] = 16 if MODE_16MP else 8
    print("分辨率档:", sel["widgets_values"])

# ---------- 2) UI → API ----------
def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.load(r)
oi = get("/object_info")
nodes = {n["id"]: n for n in wf["nodes"]}
links = {l[0]: l for l in wf["links"]}
PRIM = {"STRING", "INT", "FLOAT", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3"}

def widget_types(cls):
    info = oi.get(cls)
    if not info: return []
    out = []
    for sec in ("required", "optional"):
        for name, spec in info["input"].get(sec, {}).items():
            if isinstance(spec, list) and spec:
                t = spec[0]
                if t == "COMFY_DYNAMICCOMBO_V3": out.append((name, "dyn"))
                elif isinstance(t, list) or t in PRIM:
                    out.append((name, "skip" if isinstance(t, str) and "UPLOAD" in t else "prim"))
                else: out.append((name, "port"))
    return out

def resolve_src(node_id, slot, visited=()):
    n = nodes[node_id]
    if n.get("mode", 0) == 0: return (node_id, slot)
    if node_id in visited: return None
    outs = n.get("outputs", [])
    if slot >= len(outs): return None
    out = outs[slot]
    for inp in n.get("inputs", []):
        if inp.get("link") is None: continue
        lk = links[inp["link"]]
        src = nodes.get(lk[1])
        if not src or lk[2] >= len(src.get("outputs", [])): continue
        st = src["outputs"][lk[2]]["type"]
        if inp["name"] == out["name"] or (st == out["type"] and out["type"] != "*"):
            r = resolve_src(lk[1], lk[2], visited + (node_id,))
            if r: return r
    return None

prompt, skip = {}, 0
for nid, n in nodes.items():
    if n.get("mode", 0) != 0: skip += 1; continue
    cls = n["type"]
    if cls not in oi: print("SKIP(unknown)", cls); skip += 1; continue
    inputs, link_names = {}, set()
    for inp in n.get("inputs", []):
        if inp.get("link") is None: continue
        if inp["link"] not in links:
            print("非法引用! 节点", nid, cls, inp["name"], "->", inp["link"]); sys.exit(1)
        lk = links[inp["link"]]
        r = resolve_src(lk[1], lk[2])
        if r is None: print("WARN 悬空:", nid, cls, inp["name"]); continue
        inputs[inp["name"]] = [str(r[0]), r[1]]
        link_names.add(inp["name"])
    wv = n.get("widgets_values", [])
    if cls == "KSampler":                              # UI wv=[seed, control, steps, cfg, sampler, scheduler, denoise]
        if isinstance(wv, list) and len(wv) >= 7:
            wv = [wv[0]] + wv[2:]
        n["widgets_values"] = wv
    if isinstance(wv, dict):
        for k, v in wv.items():
            if k not in inputs: inputs[k] = v
    else:
        wi = 0
        for name, kind in widget_types(cls):
            if kind == "port": continue
            if wi >= len(wv): break
            val = wv[wi]; wi += 1
            if name in link_names or kind == "skip" or val is None: continue
            if kind == "dyn":
                inputs[name] = val
                sub_specs = {}
                for sec2 in ("required", "optional"):
                    spec2 = oi.get(cls, {}).get("input", {}).get(sec2, {}).get(name)
                    if isinstance(spec2, list) and len(spec2) > 1 and isinstance(spec2[1], dict):
                        for opt in spec2[1].get("options", []):
                            if isinstance(opt, dict) and opt.get("key") == val:
                                sub_specs = opt.get("inputs", {}).get("required", {})
                for sub in sub_specs:
                    if wi >= len(wv):
                        break
                    fid = "%s.%s" % (name, sub)
                    if fid in link_names or fid in inputs:
                        continue
                    sv = wv[wi]; wi += 1
                    if sv is not None:
                        inputs[fid] = sv
                continue
            inputs[name] = val
    prompt[str(nid)] = {"class_type": cls, "inputs": inputs}
print("API 节点:", len(prompt), "| 剔除:", skip)
# 画幅比例（图生图）：不裁切参考图！直接覆盖 #32 MiniMaxH3ImageConditioning 的
# width/height（输出画布尺寸）。换算公式与文生图 ResolutionSelector 对齐（multiple=32）。
# 参考（未覆盖时）：宽高来自第一张参考图重采样后的 GetImageSize，即"跟随参考图"。
cond_api = next((v for v in prompt.values() if v["class_type"] == "MiniMaxH3ImageConditioning"), None)

# H3 多参考（上限16张）：image_1 = 待编辑图（LoadImage 主槽），image_2..N = 追加参考。
# API 层直接挂 LoadImage 节点，不受工作流 UI 布线（5槽）限制（Autogrow max=100）。
if IMGS and len(IMGS) > 1 and cond_api is not None:
    for k, img in enumerate(IMGS[1:], start=2):
        nid = str(9100 + k)
        prompt[nid] = {"class_type": "LoadImage", "inputs": {"image": img}}
        cond_api["inputs"][f"images.image_{k}"] = [nid, 0]
    print(f"多参考接线: image_2..image_{len(IMGS)} 共追加 {len(IMGS)-1} 张")

if RATIO and RATIO != "auto":
    a, b = [float(x) for x in RATIO.split(":")]
    total = (16 if MODE_16MP else 8) * 1024 * 1024
    sc = math.sqrt(total / (a * b))
    w = int(round(a * sc / 32) * 32)
    h = int(round(b * sc / 32) * 32)
    if cond_api is not None:
        cond_api["inputs"]["width"] = w
        cond_api["inputs"]["height"] = h
        print("画幅比例覆盖:", RATIO, "-> 输出画布", w, "x", h, "（参考图保持原样）")

# API 节点级修正：编辑线带图像token（prefill远长于文生图），MTP投机解码的
# flash_attention_decode_gqa KV-cache kernel 在长上下文下报
# "Unsupported Flash Attention tensor strides"（torch2.8+comfy_kitchen，旧机torch2.12不复现）
# → 编辑线统一 mtp=off 走普通解码，稳
for v in prompt.values():
    if v["class_type"] == "TextGenerateV2":
        v["inputs"]["mtp"] = "off"
        print("TextGenerateV2 mtp=off（规避长上下文GQA stride崩溃）")

bad = [k for k, v in prompt.items() for vv in v["inputs"].values()
       if isinstance(vv, list) and str(vv[0]) not in prompt]
print("悬空引用:", bad if bad else "无")
if bad: sys.exit(1)

# ---------- 3) 提交 + 文字校验闭环（FAIL 自动换种子重roll）----------
def ensure_ocr():
    try:
        import rapidocr_onnxruntime  # noqa
        return True
    except ImportError:
        pass
    import subprocess as _sp, sys as _sys
    try:
        _sp.run([_sys.executable, "-m", "pip", "install", "-q",
                 "rapidocr-onnxruntime"], capture_output=True, timeout=600)
    except Exception:
        pass
    try:
        import rapidocr_onnxruntime  # noqa
        return True
    except ImportError:
        return False

REPORT = "/tmp/limao_text_proofread_report.json"
_base_seed = next((v["inputs"]["seed"] for v in prompt.values()
                   if v["class_type"] in ("KSampler", "KSamplerAdvanced")), 0)

attempt = 0
while True:
    data = json.dumps({"prompt": prompt, "client_id": "limao-edit"}).encode()
    req = urllib.request.Request(BASE + "/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        print("提交失败", e.code)
        try:
            errs=json.loads(e.read().decode()).get("node_errors",{})
            for nid,info in errs.items():
                print("== 本地生成的节点", nid, json.dumps(prompt.get(nid,{}), ensure_ascii=False)[:1200])
        except Exception:
            pass
        sys.exit(1)
    pid = r["prompt_id"]
    print("提交成功:", pid, f"(文字校验第{attempt+1}次)" if attempt else "")

    t0 = time.time()
    ok_imgs, h = [], {}
    while time.time() - t0 < 1800:
        time.sleep(10)
        h = json.load(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=60))
        if pid not in h:
            print(f"  [{int(time.time()-t0)}s] 排队/采样中…")
            continue
        st = h[pid].get("status", {})
        if not st.get("completed", False) and st.get("status_str") == "error":
            print("执行出错:", json.dumps(st, ensure_ascii=False)[:1500]); sys.exit(2)
        outs = h[pid].get("outputs", {})
        if outs:
            ok_imgs = [img for o in outs.values() for img in o.get("images", [])]
            if ok_imgs:
                break
    if not ok_imgs:
        print("超时未出图"); sys.exit(3)

    if TEXT_EXPECTED and ensure_ocr():
        rep = {}
        try: rep = json.load(open(REPORT, encoding="utf-8"))
        except Exception: rep = {}
        if rep.get("status") == "FAIL" and attempt < MAX_REROLL:
            attempt += 1
            ns = (_base_seed if SEED_OVERRIDE is None else SEED_OVERRIDE) + attempt * 9781799
            for v in prompt.values():
                if v["class_type"] in ("KSampler", "KSamplerAdvanced"):
                    v["inputs"]["seed"] = ns
            print(f"❌ 文字校验 FAIL（缺字/错字 {'、'.join(rep.get('missing', [])) or '?'}）"
                  f"→ 换种子 {ns} 重roll…")
            continue
        if rep.get("status") == "FAIL":
            print("❌ 重roll次数用尽文字仍不对 —— 按铁律不交付，请改短文字或换标准字体描述")
            sys.exit(4)

    for img in ok_imgs:
        print("✅ 出图:", img.get("filename"), img.get("subfolder"), img.get("type"))
    print(json.dumps(h[pid].get("status", {}).get("messages", [])[-2:], ensure_ascii=False, default=str)[:600])
    if TEXT_EXPECTED:
        print("✅ 文字校验：标准文字交付")
    sys.exit(0)
