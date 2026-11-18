# -*- coding: utf-8 -*-
"""狸猫·H3生图 t2i 验证驱动：UI工作流(subgraph展开) → API提交 → 轮询出图"""
import json, urllib.request, urllib.error, sys, time

BASE = "http://127.0.0.1:8188"
WF = "/root/ComfyUI/user/default/workflows/狸猫·H3生图/狸猫·H3生图·4K直出·文生图.json"
if "--wf" in sys.argv:
    WF = sys.argv[sys.argv.index("--wf") + 1]
MODE_16MP = "--8mp" not in sys.argv  # 默认16MP，--8mp 降档
RATIO = None
if "--ratio" in sys.argv:
    RATIO = sys.argv[sys.argv.index("--ratio") + 1]
CUSTOM_PROMPT = None
if "--prompt" in sys.argv:
    CUSTOM_PROMPT = sys.argv[sys.argv.index("--prompt") + 1]
SEED_OVERRIDE = None
if "--seed" in sys.argv:
    SEED_OVERRIDE = int(sys.argv[sys.argv.index("--seed") + 1])
TEXT_EXPECTED = None
if "--text" in sys.argv:
    TEXT_EXPECTED = sys.argv[sys.argv.index("--text") + 1]
MAX_REROLL = 3
if "--max-text-reroll" in sys.argv:
    MAX_REROLL = int(sys.argv[sys.argv.index("--max-text-reroll") + 1])

wf = json.load(open(WF))

# ---------- 1) 展开 subgraph（如有）----------
sg = (wf.get("definitions") or {}).get("subgraphs") or None
if sg:
  sg = sg[0]
if not sg:
    inodes = None
else:
  inodes = {n["id"]: n for n in json.loads(json.dumps(sg["nodes"]))}  # 唯一深拷贝
OFF = 100000
n23 = next(n for n in wf["nodes"] if n["id"] == 23)
wv23 = n23["widgets_values"]
sg_input_names = [i["name"] for i in sg["inputs"]]   # 顺序 = #23 widgets_values 顺序
assert sg_input_names[:6] == ["replace", "switch", "seed", "width", "height", "sampler_name"], sg_input_names
wv_by_name = dict(zip(sg_input_names, wv23))
if SEED_OVERRIDE is not None:
    wv_by_name["seed"] = SEED_OVERRIDE  # 重roll从该种子起步
# 外部端口连线（#23 上有 link 的输入）: name -> (src_node, src_slot, link)
ext_links_by_name = {}
for l in wf["links"]:
    if l[3] == 23:
        ext_links_by_name[n23["inputs"][l[4]]["name"]] = (l[1], l[2], l)
# widget-only 注入（外部无连线、走 widgets_values 的子输入）
IN_WIDGET_MAP = {"seed": (7, 0), "sampler_name": (7, 4), "scheduler": (7, 5),
                 "unet_name": (1, 0), "clip_name": (2, 0), "vae_name": (3, 0), "clip_name_1": (16, 0)}
for name, (nid, idx) in IN_WIDGET_MAP.items():
    val = wv_by_name.get(name)
    if val is not None:
        inodes[nid]["widgets_values"][idx] = (
            int(val) if name == "seed" else val)
if CUSTOM_PROMPT:
    pbox = next(n for n in wf["nodes"]
                if n["type"] == "PrimitiveStringMultiline" and n["id"] < OFF)
    pbox["widgets_values"][0] = CUSTOM_PROMPT

out_sources = {}  # sg output slot -> (origin_id, origin_slot)
link_map = {}     # sg link id -> 展开后顶层 link id
for l in sg["links"]:
    oid, tid = l["origin_id"], l["target_id"]
    if oid == -10:  # 输入IO：origin_slot = sg input 序号
        name = sg_input_names[l["origin_slot"]]
        nid, tslot = l["target_id"], l["target_slot"]
        if name in ext_links_by_name:
            s, ss, extl = ext_links_by_name[name]
            extl[3], extl[4] = nid + OFF, tslot            # 外部link直连内部目标
            inodes[nid]["inputs"][tslot]["link"] = extl[0]
        else:                                              # 无外部连线：撤converted，值走widgets
            inodes[nid]["inputs"][tslot]["link"] = None
        continue
    if tid == -20:  # 输出IO
        out_sources[l["target_slot"]] = (oid, l["origin_slot"])
        continue
    link_map[l["id"]] = l["id"] + OFF
    wf["links"].append([l["id"] + OFF, oid + OFF, l["origin_slot"], tid + OFF, l["target_slot"], l["type"]])

for inode in inodes.values():
    inode["id"] += OFF
    for inp in inode.get("inputs", []):                    # 内部引用统一换成新 link id
        lid = inp.get("link")
        if lid is not None and lid in link_map:
            inp["link"] = link_map[lid]
    wf["nodes"].append(inode)

# QAGate.images ← sg output 0 的内部源（VAEDecode）；#9 ← QAGate（替换遗留的 #23→#9）
src_nid, src_slot = out_sources[0]
qa = next(n for n in wf["nodes"] if n["type"] == "LimaoH3ImageQAGate")
wf["links"] = [l for l in wf["links"] if not (l[1] == 23 or l[3] == 23)]  # 清 #23 残留链
base = max(l[0] for l in wf["links"])
wf["links"].append([base + 1, src_nid + OFF, src_slot, qa["id"], 0, "IMAGE"])   # VAEDecode → QAGate
wf["links"].append([base + 2, qa["id"], 0, 9, 0, "IMAGE"])                       # QAGate → SaveImage
qa["inputs"][0]["link"] = base + 1
next(n for n in wf["nodes"] if n["id"] == 9)["inputs"][0]["link"] = base + 2

# 文字校验闸（第六道防线）：images 同源接内部 VAEDecode，expected_text 由 --text 传入
tp = next((n for n in wf["nodes"] if n["type"] == "LimaoH3TextProofread"), None)
if tp is not None:
    if TEXT_EXPECTED is not None:
        tp["widgets_values"][0] = TEXT_EXPECTED
    tpl = max(l[0] for l in wf["links"]) + 1
    wf["links"].append([tpl, src_nid + OFF, src_slot, tp["id"], 0, "IMAGE"])
    tp["inputs"][0]["link"] = tpl

# 提示词链尾（手部哨兵）→ 内部 prompt 节点 #24
hw = next(n for n in wf["nodes"] if n["type"] == "LimaoH3HandRiskWatch")
new_link = max(l[0] for l in wf["links"]) + 1
wf["links"].append([new_link, hw["id"], 0, 24 + OFF, 0, "STRING"])
inodes[24]["inputs"][0]["link"] = new_link
# 删 #23
wf["nodes"] = [n for n in wf["nodes"] if n["id"] != 23]

# 16MP：ResolutionSelector #14 widgets ['1:1 (Square)', 4, 32] → mp
res = next(n for n in wf["nodes"] if n["type"] == "ResolutionSelector")
res["widgets_values"][1] = 16 if MODE_16MP else 8
RATIO_MAP = {"1:1": "1:1 (Square)", "2:3": "2:3 (Portrait Photo)", "3:2": "3:2 (Photo)",
             "3:4": "3:4 (Portrait Standard)", "4:3": "4:3 (Standard)",
             "9:16": "9:16 (Portrait Widescreen)", "16:9": "16:9 (Widescreen)",
             "21:9": "21:9 (Ultrawide)"}
if RATIO:
    res["widgets_values"][0] = RATIO_MAP.get(RATIO, RATIO)
print("分辨率档:", res["widgets_values"])

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
    data = json.dumps({"prompt": prompt, "client_id": "limao-t2i"}).encode()
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
