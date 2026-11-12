<div align="center">

# 🐾 狸猫AI · H3视频工坊

**MiniMax H3 全流程 ComfyUI 工作流合集 · 6 大类 · 41 个**

![License](https://img.shields.io/badge/License-Limao_Proprietary-red) ![Platform](https://img.shields.io/badge/Platform-ComfyUI-blue) ![Workflows](https://img.shields.io/badge/工作流-41个-gold) ![Fingerprint](https://img.shields.io/badge/数字指纹-LM系列-orange)

</div>

---

## 🛡️ 狸猫身份牌

> **本仓库由 [狸猫AI] 制作并发行，版权归狸猫AI所有。**
>
> 全部 41 个工作流均已注入**狸猫数字指纹**，包含三层标识：
>
> | 层级 | 位置 | 内容 |
> |---|---|---|
> | 元数据层 | JSON `extra.limao` | 制作方、授权码、指纹哈希、发布时间 |
> | 节点层 | 每节点 `properties.limao_fp / limao_lic` | 狸猫指纹前缀 + LM 系列授权标识 |
> | 声明层 | 工作流内 MarkdownNote 节点 | 显性版权声明（勿删） |
>
> ⚠️ **禁止去除、修改或绕过上述标识后进行二次开发发布。**
> ⚠️ **发现无狸猫指纹的相同工作流即视为盗版，欢迎举报。**
>
> 商用授权联系：狸猫AI（授权码格式 `LM-XXXX-XXXX`）<br>GitHub：[@limao0814](https://github.com/limao0814)

## 📦 仓库内容

```
├── workflows/          # 41 个狸猫工作流（6 大分类）
│   ├── 狸猫·H3视频/            # 主打：高动态三采放大（显存治理 v3）
│   ├── 狸猫·动作迁移/          # 11 个动作迁移类
│   ├── 狸猫·人物替换换装/      # 5 个替换类
│   ├── 狸猫·数字人对口型/      # 8 个数字人类
│   ├── 狸猫·智能图像编辑/      # 7 个图像编辑类
│   └── 狸猫·视频生成/          # 6 个 Wan 视频类
├── custom_nodes/
│   └── limao-vram-tools/       # 狸猫自研显存治理节点包
│       ├── LimaoVRAMGuard      #   显存守卫（自动清理/告警）
│       ├── LimaoVAEChunkDecode #   分块解码（32帧分块）
│       └── LimaoPeakWatch      #   显存峰值监控
└── LICENSE             # 狸猫专有许可
```

## ✨ 主打特性

- **低配显卡也能跑长视频**：招牌「高动态三采放大」工作流，从 768p 草稿到高清成片一步到位，全程自动治理显存，消费级显卡即可上手
- **武戏一键出片**：打斗、特技动作内置专属 LoRA，选好模板发即用，不用手动调参
- **拿来就能用**：41 个工作流逐一实测校验，模型依赖齐备、开箱即跑

## 🚀 安装

```bash
# 1. 工作流：复制到 ComfyUI 工作流目录
cp -r workflows/狸猫* /path/to/ComfyUI/user/default/workflows/

# 2. 自研节点包
cp -r custom_nodes/limao-vram-tools /path/to/ComfyUI/custom_nodes/
```

模型依赖见各工作流内说明节点（官方来源：HuggingFace `Comfy-Org/MiniMax-H3` 等公开仓库）。

## 📄 许可

本项目采用 [狸猫专有许可](LICENSE) —— 个人使用自由，**去除指纹二次发布被明确禁止**。

---

<div align="center">

**© 狸猫AI · H3视频工坊** · 狸猫出品，必属精品 🐾

</div>
