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
│   ├── 狸猫·H3视频/            # 主打：全域参考锻造·双采放大（旗舰）
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
├── limao-app/                  # 实例服务三件套（开机全自动）
│   ├── autostart.sh            #   开机自启入口（customer.cmd.sh → /etc/autodl.sh → 本脚本）
│   ├── gateway6006.py          #   6006 常驻反向代理网关（就绪前亮欢迎页，HTTP+WS 全穿透，零空窗）
│   └── panel6008.py            #   6008 狸猫专属进入面板（实时状态 + 一键进工作台）
└── LICENSE             # 狸猫专有许可
```

## 🏆 旗舰工作流：狸猫·H3·全域参考锻造·从零版

**双链拓扑**：一采/二采各一条独立 LoRA 链；一采重档（Combat 0.7 / turbo 0.7 / Dasiwa 0.9 / Motion 0.7）无块稀疏，二采轻档（Combat 0.49 / Dasiwa 0.55 / turbo 0.65 / Motion 0.25）尾接块稀疏。

### 四档配方（均实测零缺陷）

| 档位 | 分辨率 | LoRA 配置 | 适用 |
|---|---|---|---|
| 文戏标准 | 1536 级 | 基础链 | 对话、走位、情绪 |
| 武戏档 | 1536 级 | +LMS r64 二采 + #61 双阶段 sigma | 打斗、特技（建议 5 秒短片，15 秒全程约 2 小时） |
| 满配 9+3+3 | 1536×960 | 九图 + 三音频 + 三视频参考 | 全域参考 |
| 2K 档 | 2112×1152 | 四件套（IC/Pika/HyperFlow/LMS）全启用 | 高清交付 |

### 2K 短跑配方（显存数学定版）

- 2K×15 秒全长 = 362 帧，二采单次激活申请 15.29G，48G 卡必爆 → **2K 上限约 52 帧**
- **定版方案：`DUR=2.5`（→73 帧，17n+5 合规网格）**，约 12 分钟出片，零 OOM
- 工具：`tools/ab_run_2k_sprint.py`（提交层特判，只改 #40 时长，工作流 json 保持 15 秒不动）
- 实例侧用法：`DUR=2.5 python /tmp/ab_run.py limao`

### 官方校验铁律（踩坑总结）

1. 视频参考 **≥48 帧**（26 帧会被拒），建议 4fps 降采样防显存爆
2. 二采装配宽高必须接放大器 `width/height` INT 输出口（slot 1/2）
3. converted 连线的 widget 留占位不删除（#45 需与 #44 同构 13 项）
4. 换结构/参数必须重启清 ComfyUI 结构缓存才真跑
5. ffmpeg 不能原地读写同一文件（静默失败）

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
