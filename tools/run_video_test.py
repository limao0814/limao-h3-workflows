# -*- coding: utf-8 -*-
"""狸猫·H3主打流（视频）新机测试驱动：UI工作流 → API提交 → 轮询出片"""
import json, urllib.request, urllib.error, sys, time

BASE = "http://127.0.0.1:8188"
WF = "/root/ComfyUI/user/default/workflows/狸猫·H3视频/狸猫H3工作流.json"
CLIENT_ID = "limao-video"
TIMEOUT = 7200  # 视频生成最长2小时

wf = json.load(open(WF))
print("工作流:", WF, "| 节点:", len(wf["nodes"]), "| 链:", len(wf["links"]))

# 显存不足降档：--pmp 0.35 把 #29 ResolutionSelector 的规模系数从 0.6 调小
# （一采/二采按比例同步缩小，二采=一采latent×1.5自动跟随）
if "--pmp" in sys.argv:
    PMP = float(sys.argv[sys.argv.index("--pmp") + 1])
    sel = next(n for n in wf["nodes"] if n["type"] == "ResolutionSelector")
    old = sel["widgets_values"][1]
    sel["widgets_values"][1] = PMP
    print(f"分辨率降档: #29 系数 {old} -> {PMP}")

# --nosecond：旁路二采三件套（latent放大/二采协调/二采采样），
# #303 AV latent 存档经旁路穿透落到一采输出 → 0.6MP 一采直出
# （同旧机 12 秒汉服甩袖视频 1024x640 的产出路径）
if "--nosecond" in sys.argv:
    _nd = {n["id"]: n for n in wf["nodes"]}
    sc = sorted(n["id"] for n in wf["nodes"] if n["type"] == "SamplerCustomAdvanced")
    targets = set()
    for n in wf["nodes"]:
        if n["type"] in ("MiniMaxH3LearnedLatentUpscaleT8Advanced", "MiniMaxH3TwoPassLatentReconcileT8Advanced"):
            targets.add(n["id"])
    if len(sc) >= 2: targets.add(sc[1])
    for nid in targets:
        _nd[nid]["mode"] = 4
    print(f"二采旁路: 节点 {sorted(targets)} → 一采直出")
    # #303 AV latent 存档显式改接一采 denoised_output（穿透解析会错误落到
    # #14 二采模板latent，必须显式改链）
    nd303 = next(n for n in wf["nodes"] if n["type"] == "LimaoH3AVLatentSave")
    first_sampler = sc[0]
    for inp in nd303.get("inputs", []):
        if inp.get("name") == "av_latent":
            new_id = max((l[0] for l in wf["links"]), default=0) + 1
            wf["links"].append([new_id, first_sampler, 1, nd303["id"], 0, "LATENT"])
            inp["link"] = new_id
            print(f"#303.av_latent 显式改接 #{first_sampler} 槽1(denoised_output)")
if "--dryrun" in sys.argv:
    pass  # 占位，转换完成后退出

# ImageCompare 等 socketless 预览组件（UI专用）API 校验必挂 → 转换前 bypass
for n in wf["nodes"]:
    if n["type"] == "ImageCompare" and n.get("mode", 0) == 0:
        n["mode"] = 4
        print("ImageCompare 预览节点已 bypass（API线不需要）")

# ---------- UI → API ----------
def get(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
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

# UI原生Primitive节点（Float/Int/String/Boolean等，不在object_info）：前端转API时
# 内联为字面量。这里同样处理——消费方直接拿widget值，不挂节点引用。
PRIM_UI = {}
for nid, n in nodes.items():
    if n["type"] in ("Float", "Int", "String", "Boolean", "StringMultiline",
                     "PrimitiveString", "PrimitiveStringMultiline") \
            and n.get("mode", 0) == 0 and n.get("widgets_values"):
        PRIM_UI[nid] = n["widgets_values"][0]
if PRIM_UI:
    print("Primitive字面量:", PRIM_UI)

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
        if r is None:
            if lk[1] in PRIM_UI:
                inputs[inp["name"]] = PRIM_UI[lk[1]]
                link_names.add(inp["name"])
                continue
            print("WARN 悬空:", nid, cls, inp["name"]); continue
        if r[0] in PRIM_UI:
            inputs[inp["name"]] = PRIM_UI[r[0]]
            link_names.add(inp["name"])  # 修复：内联Primitive字面量也必须登记，
            continue                       # 否则widget回填会用节点残留widget值覆盖（汉服prompt污染根因）
        inputs[inp["name"]] = [str(r[0]), r[1]]
        link_names.add(inp["name"])
    wv = n.get("widgets_values", [])
    if cls in ("KSampler", "KSamplerAdvanced"):        # UI wv=[seed, control, steps, cfg, sampler, scheduler, denoise]
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
    # COMBO / 动态组合件 显示名 → API枚举值（UI widget 可能存 "Ref2VA — 参考生音视频" 这类带说明的显示串）
    info = oi.get(cls)
    if info:
        for sec in ("required", "optional"):
            for name, spec in info["input"].get(sec, {}).items():
                if name not in inputs:
                    continue
                opts = None
                if isinstance(spec, list) and spec and isinstance(spec[0], list):
                    opts = spec[0]                          # 普通COMBO
                elif isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], dict) \
                        and spec[1].get("options"):         # COMBO带options说明 / COMFY_DYNAMICCOMBO_V3
                    opts = [o.get("key") if isinstance(o, dict) else o for o in spec[1]["options"]]
                if opts and isinstance(inputs[name], str) and inputs[name] not in opts:
                    cand = inputs[name].split(" — ")[0].strip()
                    if cand in opts:
                        print(f"COMBO映射: #{nid} {cls}.{name} '{inputs[name]}' -> '{cand}'")
                        inputs[name] = cand
                    else:
                        print(f"⚠️ COMBO不匹配: #{nid} {cls}.{name} '{inputs[name]}' 不在 {opts[:8]}")
print("API 节点:", len(prompt), "| 剔除:", skip)

# 长上下文 FA stride 崩溃保险：视频线也统一 mtp=off
for v in prompt.values():
    if v["class_type"] == "TextGenerateV2":
        v["inputs"]["mtp"] = "off"
        print("TextGenerateV2 mtp=off（长上下文保险）")

bad = [k for k, v in prompt.items() for vv in v["inputs"].values()
       if isinstance(vv, list) and str(vv[0]) not in prompt]
print("悬空引用:", bad if bad else "无")
if bad: sys.exit(1)

# ---------- 提交 + 轮询 ----------
if "--dryrun" in sys.argv:
    json.dump(prompt, open('/root/dryrun_prompt.json','w'), ensure_ascii=False, indent=1)
    print('DRYRUN: 节点数', len(prompt), '-> /root/dryrun_prompt.json'); sys.exit(0)
data = json.dumps({"prompt": prompt, "client_id": CLIENT_ID}).encode()
req = urllib.request.Request(BASE + "/prompt", data=data, headers={"Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req, timeout=60))
except urllib.error.HTTPError as e:
    print("提交失败", e.code)
    try:
        errs = json.loads(e.read().decode()).get("node_errors", {})
        for nid, info in errs.items():
            print("== 节点", nid, json.dumps(info, ensure_ascii=False)[:800])
    except Exception:
        pass
    sys.exit(1)
pid = r["prompt_id"]
print("提交成功:", pid)

t0 = time.time()
last_nodes = -1
while time.time() - t0 < TIMEOUT:
    time.sleep(20)
    try:
        h = json.load(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=60))
    except Exception as e:
        print(f"  [{int(time.time()-t0)}s] history查询异常 {e}")
        continue
    if pid not in h:
        # 进度：查queue看running节点
        try:
            q = json.load(urllib.request.urlopen(f"{BASE}/queue", timeout=30))
            msgs = [e for e in q.get("queue_running", [])]
            print(f"  [{int(time.time()-t0)}s] 执行中… running={len(q['queue_running'])} pending={len(q['queue_pending'])}")
        except Exception:
            print(f"  [{int(time.time()-t0)}s] 执行中…")
        continue
    st = h[pid].get("status", {})
    if not st.get("completed", False) and st.get("status_str") == "error":
        print("执行出错:", json.dumps(st, ensure_ascii=False)[:1500]); sys.exit(2)
    if st.get("status_str") == "success" and st.get("completed", False):
        print(f"✅ 执行成功 {int(time.time()-t0)}s")
        for o in h[pid].get("outputs", {}).values():
            for key in ("images","gifs","videos","latents","audio"):
                for f in o.get(key,[]) or []:
                    print("   产出:", f.get("filename"), f.get("subfolder"))
        sys.exit(0)
    outs = h[pid].get("outputs", {})
    if outs:
        files = [img for o in outs.values() for img in o.get("images", [])]
        if files:
            el = int(time.time() - t0)
            print(f"✅ 完成! 耗时 {el}s ({el//60}m{el%60}s)")
            for img in files:
                print("   产出:", img.get("filename"), img.get("subfolder"), img.get("type"))
            sys.exit(0)
print("超时未出片")
sys.exit(3)
