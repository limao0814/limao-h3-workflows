# 狸猫·原版BUNNY优化版构建：保留全部画质武器 + 植入自研节点
# 输出: /root/ComfyUI/user/default/workflows/狸猫·H3视频/狸猫H3工作流.json
# (ab_run limao 从该路径提交)
import json, os, shutil

SRC = "/tmp/bunny/BUNNY_H3_高动态双采放大专属_FL2VA.json"
DST = "/root/ComfyUI/user/default/workflows/狸猫·H3视频/狸猫H3工作流.json"
BAK = "/tmp/backup_狸猫H3工作流_stage1h.json"

wf = json.load(open(SRC))
nodes = {n["id"]: n for n in wf["nodes"]}
next_link = max(l[0] for l in wf["links"]) + 1

def add_link(src, sslot, dst, dslot, typ):
    global next_link
    lid = next_link; next_link += 1
    wf["links"].append([lid, src, sslot, dst, dslot, typ])
    return lid

def port(node, name, typ, lid):
    node["inputs"].append({"name": name, "type": typ, "link": lid})

def add_node(nid, ntype, pos, widgets=None, inputs=None):
    n = {"id": nid, "type": ntype, "pos": pos, "size": [300, 120], "flags": {},
         "order": 300+nid, "mode": 0, "inputs": inputs or [],
         "outputs": [], "properties": {}, "widgets_values": widgets or []}
    wf["nodes"].append(n)
    return n

# ---- 0) 备份旧工作流 ----
if os.path.exists(DST) and not os.path.exists(BAK):
    shutil.copy(DST, BAK)
    print("旧stage1h工作流已备份:", BAK)

# ---- 1) 素材替换：2张汉服参考图+1段舞曲（与素材库对齐，不硬凑9+3）----
IMG_SLOTS = [6, 35, 36, 37, 86, 87, 88, 89, 90]
REF_IMGS = ["ref_image_1.png", "ref_image_2.png"] * 5
for i, nid in enumerate(IMG_SLOTS):
    n = nodes[nid]
    w = n["widgets_values"]
    w[0] = REF_IMGS[i]
    if len(w) > 1: w[1] = "image"
    # 只激活前2张（素材库就2张）；其余保持BUNNY原版bypass，防重复图警告与token浪费
    if i >= 2: n["mode"] = 4
    else: n["mode"] = 0
AUD_SLOTS = [97, 127, 128]
for i, nid in enumerate(AUD_SLOTS):
    n = nodes[nid]
    n["widgets_values"][0] = "1.mp3"
    # 只激活第1个音频槽（3槽同曲会触发时长超预算风险）
    n["mode"] = 0 if i == 0 else 4
print("素材已替换: 图=#6,#35(ref_image_1/2) 激活, 其余bypass; 音频=#97(1.mp3)激活, 其余bypass")

# ---- 1.5) prompt替换：BUNNY原版#49是动漫少女提示词，必须换成汉服任务 ----
HANFU_PROMPT = ("A graceful young Chinese woman in traditional red-and-white Hanfu "
                "dances gracefully on ancient stone steps in a sunlit garden, "
                "flowing sleeves and skirt, cinematic lighting, shallow depth of field, "
                "realistic photography, film grain texture "
                "(character appearance and outfit follow the reference images exactly)")
nodes[49]["widgets_values"][0] = HANFU_PROMPT
print("prompt已替换为汉服任务")

# ---- 1.6) 时长：#27 PrimitiveFloat 10→15秒（length公式自动吸附17n+5网格→362帧） ----
DUR = float(os.environ.get("HANFU_DUR", "15"))
nodes[27]["widgets_values"] = [DUR]
print(f"时长已设为 {DUR}s")

# ---- 2) 时长/参数：保持124帧(5.17s)单段验证；画布0.6MP×1.5²≈1.4MP ----
# prompt沿用原版(红汉服旋转+电影光)，无需改

# ---- 3) 植入自研节点 ----
# 300 图审计（硬闸）：激活的2张真图 + 重复引用补齐required槽
n300 = add_node(300, "LimaoH3RefImageAudit", [-1300, -600])
AUD_IMG_SRCS = [6, 35] + [6] * 7   # image_3~9重复引用#6（仅审计枝，不喂模型）
for i, nid in enumerate(AUD_IMG_SRCS):
    lid = add_link(nid, 0, 300, i, "IMAGE")
    port(n300, f"image_{i+1}", "IMAGE", lid)
# 302 清道夫：插在 放大器#13 → 二采Reconcile#15.learned_latent 之间
n302 = add_node(302, "LimaoH3MemorySweep", [200, 900], widgets=[True, True, True])
port(n302, "anything", "*", add_link(13, 0, 302, 0, "*"))
n302["outputs"] = [{"name": "output", "type": "*", "links": []}]
lid15 = add_link(302, 0, 15, 0, "LATENT")
old15 = None
for inp in nodes[15]["inputs"]:
    if inp["name"] == "learned_latent":
        old15 = inp["link"]; inp["link"] = lid15
if old15 is not None and old15 in wf.get("links", []) :
    pass  # 旧链接留在表里不影响转换(ab_run按inputs.link解析)
print("清道夫已插入 #13 → #302 → #15.learned_latent")
# 303 AV latent落盘（二采输出直接落盘，替代内置解码=两段式防交接崩溃）
n303 = add_node(303, "LimaoH3AVLatentSave", [900, 1100], widgets=["hanfu_bunny_av"])
port(n303, "av_latent", "LATENT", add_link(19, 0, 303, 0, "LATENT"))
n303["outputs"] = []
print("AVLatentSave已挂 #19 输出")
# 304 二采内置解码链 bypass（改走独立队列H3KitVAEDecodeTiled）
for nid in (216, 51, 98):
    nodes[nid]["mode"] = 4
print("#216/#51/#98 内置解码已bypass")

json.dump(wf, open(DST, "w"), ensure_ascii=False)
print("优化版工作流已写入:", DST)
print("节点总数:", len(wf["nodes"]))
