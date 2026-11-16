# -*- coding: utf-8 -*-
"""狸猫·H3生图·4K直出 工作流构建脚本
=====================================
基于 ComfyUI 官方 MiniMax-H3-Image 模板（tools/templates_official/ 原件存档）
做狸猫化改造，产出 workflows/狸猫·H3生图/ 两个成品：

  1) 狸猫·H3生图·4K直出·文生图.json   （t2i 模板 + 提示词体检 + 出图硬闸）
  2) 狸猫·H3生图·4K直出·图像编辑.json （edit 模板 + 4K画布 + 提示词体检 + 出图硬闸 + 16图审计）

改造依据 = 社区实测爆料毛病的逐条对策：
  A. 分辨率敏感（<8MP 脸/手/小人伪影，8MP+ 才稳）→ 分辨率选择器 4MP→16MP 直出（4K 档）
  B. 提示词敏感（堆砌词降质/无负面词/短文字需引号）→ 全线串接 LimaoH3ImagePromptGuard
  C. 出图后无人把关 → 全线串接 LimaoH3ImageQAGate（8MP 伪影线 / 16MP 最佳线分级放行）
  D. 多图融合角色漂移 → LimaoH3Ref16Audit 审计 + <Picture N> 锁位提醒
  E. 官方模板无显性质检 → SaveImage 前全部过闸

模型文件（ComfyUI models/，ComfyUI ≥0.45.0 + 模板包 ≥0.11.104）：
  diffusion_models/minimax_h3_image_pruned_int8_convrot.safetensors  (~21GB INT8)
  text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
  text_encoders/qwen3.5_9b_w4a8_gptq.safetensors（提示词扩写 PE 轻量版）
  vae/minimax_h3_image_vae_fp16.safetensors

用法：python3 tools/build_limao_image.py
"""
import copy
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "templates_official")
DST = os.path.join(ROOT, "workflows", "狸猫·H3生图")

# 指纹与授权（按工作流内容确定性生成，与仓库既有模式一致）
RELEASE = "LIMAO-WF-20261115-R1"

LIMAO_NOTICE = (
    "◆ 狸猫AI · H3生图 · 4K直出系列\n"
    "本工作流由 狸猫AI 制作并发行，受狸猫数字指纹保护（extra.limao / properties.limao_fp），"
    "禁止去除指纹后二次开发、复制、转发或发布至其他平台。商用授权联系狸猫AI（LM-XXXX-XXXX）。\n\n"
    "◆ 为什么默认 16MP 直出（4K）\n"
    "H3-Image 社区实测：8MP 以下（尤其 2MP/4MP）脸、手、背景小人容易出伪影，"
    "8MP 以上才明显变好 —— 所以本工作流把官方模板的 4MP 默认档直接拉到 16MP（4K 最佳工作区）。\n"
    "显存不够时可临时降回 8MP，出图后「狸猫·出图硬闸」会给出分级提示。\n\n"
    "◆ 提示词三条铁律（模型无负面提示词）\n"
    "1. 先交代图像类型（街拍照片 / 70年代电影帧 / 产品渲染图…），再描述内容；\n"
    "2. 禁用堆砌词（stunning / 8k / masterpiece…），写了反而降质；\n"
    "3. 图内文字用引号包住并保持简短（小字必乱码，长文案请后期加）。\n"
    "正向里写『不要X』会画出X —— 负面诉求一律改写成正向描述。\n\n"
    "◆ 多参考图\n"
    "参考图以 <Picture 1>…<Picture 16> 寻址（上传顺序即编号）。"
    "多图融合实测有角色漂移：主角色务必放 <Picture 1> 并在提示词点名锁定。"
    "接了「狸猫·16图参考审计」的会在面板出合规报告。"
)

LIMAO_T2I_PROMPT = (
    "A cinematic photograph of a graceful young Chinese woman in traditional red-and-white Hanfu, "
    "standing on ancient stone steps in a sunlit garden, flowing sleeves, shallow depth of field, "
    "natural film grain (character appearance follows <Picture 1> exactly)"
)


def fingerprint(payload: str):
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return h[:16], f"LM-{h[16:20].upper()}-{h[20:24].upper()}"


def stamp(wf, name):
    payload = name + json.dumps(wf["nodes"], sort_keys=True, ensure_ascii=False)
    fp, lic = fingerprint(payload)
    for n in wf["nodes"]:
        props = n.setdefault("properties", {})
        props["limao_fp"] = fp
        props["limao_lic"] = lic
    wf.setdefault("extra", {})["limao"] = {
        "product": "狸猫AI",
        "release": RELEASE,
        "license": lic,
        "fingerprint": fp,
        "notice": "狸猫AI专属工作流，受狸猫数字指纹保护，禁止二次开发、复制、转发或发布至其他平台",
    }
    return fp, lic


# 实例文件适配（狸猫 4080S 构建机现状）：
# - 扩散模型 INT8 在 diffusion_models/minimax/ 子目录（共享库软链，零下载）
# - 文本编码器盘上只有 int4_convrot（int8 版 32G 系统盘放不下）——扩散模型 int8 不变，
#   编码器 int4 对画质影响远小于扩散模型，实测可接受
# - PE 扩写 qwen3.5_9b_w4a8_gptq 缺货 → 用盘上 qwen3.5_4b_bf16 替换（t2i 默认关 PE 不受影响）
ADAPT = {
    "minimax_h3_image_pruned_int8_convrot.safetensors":
        "minimax/minimax_h3_image_pruned_int8_convrot.safetensors",
    "qwen3vl_32b_minimax_h3_int8_convrot.safetensors":
        "qwen3vl_32b_minimax_h3_int4_convrot.safetensors",
    "qwen3.5_9b_w4a8_gptq.safetensors":
        "qwen3.5_4b_bf16.safetensors",
}

def adapt_filenames(wf):
    n_adapted = 0
    for n in wf["nodes"]:
        wv = n.get("widgets_values")
        if isinstance(wv, list):
            for i, v in enumerate(wv):
                if isinstance(v, str) and v in ADAPT:
                    wv[i] = ADAPT[v]
                    n_adapted += 1
    # subgraph 定义里的节点同样处理
    for sg in wf.get("definitions", {}).get("subgraphs", []):
        for n in sg["nodes"]:
            wv = n.get("widgets_values")
            if isinstance(wv, list):
                for i, v in enumerate(wv):
                    if isinstance(v, str) and v in ADAPT:
                        wv[i] = ADAPT[v]
                        n_adapted += 1
    return n_adapted


class Ctx:
    def __init__(self, wf):
        self.wf = wf
        self.nid = wf["last_node_id"]
        self.lid = wf["last_link_id"]
        self.nodes = {n["id"]: n for n in wf["nodes"]}

    def node(self, itype, widgets=None, pos=(-600, 600), inputs=None, outputs=None):
        self.nid += 1
        n = {"id": self.nid, "type": itype, "pos": pos, "size": [320, 140],
             "flags": {}, "order": self.nid, "mode": 0,
             "inputs": inputs or [], "outputs": outputs or [],
             "properties": {}, "widgets_values": widgets or []}
        self.wf["nodes"].append(n)
        self.nodes[self.nid] = n
        return n

    def link(self, src, sslot, dst, dslot, typ):
        self.lid += 1
        self.wf["links"].append([self.lid, src, sslot, dst, dslot, typ])
        out = self.nodes[src]["outputs"][sslot]
        out.setdefault("links", []).append(self.lid)
        self.nodes[dst]["inputs"][dslot]["link"] = self.lid
        return self.lid

    def note(self, pos=(-450, -350)):
        n = self.node("MarkdownNote", [LIMAO_NOTICE], pos=pos)
        n["size"] = [520, 460]
        n["title"] = "狸猫AI · 数字指纹与使用须知（勿删）"
        return n


def relink(wf, old_src, old_sslot, new_src, new_sslot, dst, dslot, typ):
    """把 old→dst 的连线改为 new→dst（new 由 old 供给）。"""
    for l in wf["links"]:
        if l[1] == old_src and l[2] == old_sslot and l[3] == dst and l[4] == dslot:
            l[1], l[2] = new_src, new_sslot
            new_out = None
            for n in wf["nodes"]:
                if n["id"] == new_src:
                    new_out = n["outputs"][new_sslot]
            new_out.setdefault("links", []).append(l[0])
            return l[0]
    raise KeyError(f"link {old_src}:{old_sslot}->{dst}:{dslot} not found")


# ---------------------------------------------------------------------------
# 1) 文生图：t2i 模板（subgraph 封装）
# ---------------------------------------------------------------------------
def build_t2i():
    wf = json.load(open(os.path.join(SRC, "t2i.json"), encoding="utf-8"))
    print("实例文件适配:", adapt_filenames(wf), "处")
    ctx = Ctx(wf)

    # A. 4K直出：ResolutionSelector 4MP → 16MP（比例选项沿用官方支持集）
    res = ctx.nodes[14]
    assert res["type"] == "ResolutionSelector", res["type"]
    res["widgets_values"][1] = 16

    # B. 提示词体检 + 手部哨兵串接：用户prompt → PromptGuard → HandRiskWatch → subgraph.replace
    pg = ctx.node("LimaoH3ImagePromptGuard", [LIMAO_T2I_PROMPT, "体检并自动修复", "无参考图"],
                  pos=(-950, 120),
                  inputs=[{"name": "prompt", "type": "STRING", "link": None}],
                  outputs=[{"name": "prompt", "type": "STRING", "links": []}])
    hw = ctx.node("LimaoH3HandRiskWatch", ["", "自动增强"], pos=(-650, 120),
                  inputs=[{"name": "prompt", "type": "STRING", "link": None}],
                  outputs=[{"name": "prompt", "type": "STRING", "links": []}])
    pbox = ctx.node("PrimitiveStringMultiline", [LIMAO_T2I_PROMPT], pos=(-1300, 120),
                    outputs=[{"name": "STRING", "type": "STRING", "links": []}])
    ctx.link(pbox["id"], 0, pg["id"], 0, "STRING")
    ctx.link(pg["id"], 0, hw["id"], 0, "STRING")
    # subgraph 节点 #23 的 replace 槽原本吃 widget 默认值（无连线），
    # 接线后 prompt 由 HandRiskWatch 供给（widget 变为备用默认，不影响）。
    lid = ctx.lid + 1
    ctx.lid = lid
    wf["links"].append([lid, hw["id"], 0, 23, 0, "STRING"])
    hw["outputs"][0]["links"].append(lid)
    sub_in = [i for n in wf["nodes"] if n["id"] == 23 for i in n["inputs"] if i["name"] == "replace"][0]
    sub_in["link"] = lid

    # C. 出图硬闸：QAGate 输出→SaveImage；其输入(images)在运行时由
    #    run_t2i.py 展开 subgraph 后接内部 VAEDecode（构建期跨不过 subgraph 边界）
    qa = ctx.node("LimaoH3ImageQAGate", ["16MP直出(推荐)", 8], pos=(300, 300),
                  inputs=[{"name": "images", "type": "IMAGE", "link": None}],
                  outputs=[{"name": "images", "type": "IMAGE", "links": []}])

    # E. 保存前缀 + 版权声明
    ctx.nodes[9]["widgets_values"] = ["limao_h3_image_t2i_4k"]
    ctx.note(pos=(-460, -420))

    fp, lic = stamp(wf, "狸猫·H3生图·4K直出·文生图")
    out = os.path.join(DST, "狸猫·H3生图·4K直出·文生图.json")
    json.dump(wf, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ {out}  fp={fp} lic={lic} nodes={len(wf['nodes'])}")
    return out


# ---------------------------------------------------------------------------
# 2) 图像编辑：edit 模板（平铺 27 节点）
# ---------------------------------------------------------------------------
def build_edit():
    wf = json.load(open(os.path.join(SRC, "edit.json"), encoding="utf-8"))
    print("实例文件适配:", adapt_filenames(wf), "处")
    ctx = Ctx(wf)

    # A. 4K直出：#56 scale total pixels 4MP → 16MP（源图抬到 4K 画布再采样）
    n56 = ctx.nodes[56]
    assert n56["type"] == "ResizeImageMaskNode", n56["type"]
    assert n56["widgets_values"][0] == "scale total pixels"
    n56["widgets_values"][1] = 16

    # B. 提示词体检 + 手部哨兵串接：#43 指令 → PromptGuard → HandRiskWatch → (#41.on_false + #40.replace)
    pg = ctx.node("LimaoH3ImagePromptGuard", ["", "体检并自动修复", "有参考图(锁定主角色)"],
                  pos=(-1200, 1400),
                  inputs=[{"name": "prompt", "type": "STRING", "link": None}],
                  outputs=[{"name": "prompt", "type": "STRING", "links": []}])
    hw = ctx.node("LimaoH3HandRiskWatch", ["", "自动增强"], pos=(-950, 1400),
                  inputs=[{"name": "prompt", "type": "STRING", "link": None}],
                  outputs=[{"name": "prompt", "type": "STRING", "links": []}])
    l43a = next(l for l in wf["links"] if l[1] == 43 and l[3] == 41)
    l43a[1], l43a[2] = hw["id"], 0                  # #41.on_false ← 手部哨兵输出
    l43b = next(l for l in wf["links"] if l[1] == 43 and l[3] == 40)
    l43b[1], l43b[2] = hw["id"], 0                  # #40.replace ← 手部哨兵输出
    ctx.link(43, 0, pg["id"], 0, "STRING")          # #43指令 → 提示词体检
    ctx.link(pg["id"], 0, hw["id"], 0, "STRING")    # 体检 → 手部哨兵
    # edit 模板必有参考图（源图即 <Picture 1>），主角色锁定默认开启

    # C. 出图硬闸：#42 VAEDecode → QAGate.images；QAGate → #9 SaveImage
    qa = ctx.node("LimaoH3ImageQAGate", ["16MP直出(推荐)", 8], pos=(300, 300),
                  inputs=[{"name": "images", "type": "IMAGE", "link": None}],
                  outputs=[{"name": "images", "type": "IMAGE", "links": []}])
    l42 = next(l for l in wf["links"] if l[1] == 42 and l[3] == 9)
    l42[3], l42[4] = qa["id"], 0                    # 42 → QAGate.images
    qa["inputs"][0]["link"] = l42[0]
    ctx.link(qa["id"], 0, 9, 0, "IMAGE")            # QAGate → SaveImage

    # D. 16图参考审计：源图 LoadImage 挂审计（纯展示，不占主链）
    aud = ctx.node("LimaoH3Ref16Audit", pos=(-1300, 300))
    for i in range(1, 17):
        aud["inputs"].append({"name": f"image_{i}", "type": "IMAGE", "link": None})
    ctx.link(45, 0, aud["id"], 0, "IMAGE")

    # E. 保存前缀 + 版权声明
    ctx.nodes[9]["widgets_values"] = ["limao_h3_image_edit_4k"]
    ctx.note(pos=(-460, -420))

    fp, lic = stamp(wf, "狸猫·H3生图·4K直出·图像编辑")
    out = os.path.join(DST, "狸猫·H3生图·4K直出·图像编辑.json")
    json.dump(wf, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ {out}  fp={fp} lic={lic} nodes={len(wf['nodes'])}")
    return out


if __name__ == "__main__":
    os.makedirs(DST, exist_ok=True)
    a = build_t2i()
    b = build_edit()
    print("\n两条生图工作流构建完成。开机验证清单：")
    print("  1. ComfyUI ≥0.45.0、模板包 ≥0.11.104")
    print("  2. models 四件套就位（见脚本头注释），limao-h3-suite 已装")
    print("  3. 32G 卡先跑 t2i 16MP 单张，盯显存峰值；爆了退 8MP 档再试")
    print("  4. edit 线注意 #56=16MP 是源图放大档，源图过小可先降 8MP 试链路")
