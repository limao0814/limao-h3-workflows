<div align="center">

# 🐾 狸猫AI · H3视频工坊

**MiniMax H3 全流程 ComfyUI 工作流合集 · 7 大类 · 40 个正式工作流**（另有 9 份历史版本存档）

![License](https://img.shields.io/badge/License-Limao_Proprietary-red) ![Platform](https://img.shields.io/badge/Platform-ComfyUI-blue) ![Workflows](https://img.shields.io/badge/工作流-40个-gold) ![Fingerprint](https://img.shields.io/badge/数字指纹-LM系列-orange)

</div>

---

## 🛡️ 狸猫身份牌

> **本仓库由 [狸猫AI] 制作并发行，版权归狸猫AI所有。**
>
> 全部 40 个正式工作流均已注入**狸猫数字指纹**，包含三层标识：
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
├── workflows/          # 44 个狸猫工作流（7 大分类）+ 9 份历史版本存档
│   ├── 狸猫·H3生图/            # 6 个：画布现役 4 套（文生图 / 文生图·自然真实风格 / 图生图·16图参考 / 图生图·自然真实风格）+ 4K直出双工作流（文生图/图像编辑）
│   ├── 狸猫·H3视频/            # 1 个主打：狸猫H3工作流（现役版：三节点合一 + 9图/3音频参考直连 + 双采二阶放大）+ 2K交付版 + 存档/ 8 份历史版本
│   ├── 狸猫·动作迁移/          # 12 个动作迁移类
│   ├── 狸猫·人物替换换装/      # 5 个替换类
│   ├── 狸猫·数字人对口型/      # 7 个数字人类
│   ├── 狸猫·智能图像编辑/      # 7 个图像编辑类
│   └── 狸猫·视频生成/          # 6 个 Wan 视频类
├── custom_nodes/
│   ├── limao-h3-suite/         # 狸猫自研 H3 工坊节点套件（17 个节点）
│   │   ├── LimaoH3ModelSentinel    #   模型哨兵（存在性/一致性校验）
│   │   ├── LimaoH3RefImageAudit    #   参考图审计（视频9图逐张校验）
│   │   ├── LimaoH3RefVideoAudit    #   参考视频审计
│   │   ├── LimaoH3RefAudioAudit    #   参考音频审计
│   │   ├── LimaoH3FrameBridge      #   帧桥（参考帧桥接）
│   │   ├── LimaoH3SeedForge        #   种子锻炉（确定性种子）
│   │   ├── LimaoH3VRAMGuard        #   显存守卫（自动清理/告警）
│   │   ├── LimaoH3MemorySweep      #   显存清道夫（链路中间释放峰值）
│   │   ├── LimaoH3AVLatentSave     #   AV潜空间落盘（采样/解码两段式解耦）
│   │   ├── LimaoH3AVLatentLoad     #   AV潜空间回载（阶段2独立解码）
│   │   ├── LimaoH3ImagePromptGuard #   提示词体检（生图）
│   │   ├── LimaoH3ImageQAGate      #   出图硬闸（质检拦截）
│   │   ├── LimaoH3Ref16Audit       #   16图参考审计（图生图逐张校验）
│   │   ├── LimaoH3HandRiskWatch    #   手部风险哨兵
│   │   ├── LimaoH3TextProofread    #   文字校验闸（RapidOCR逐字比对）
│   │   ├── LimaoH3WHCalc           #   输出画幅计算器（实时算式预览）
│   │   └── LimaoH3VideoParams      #   视频参数枢纽（分辨率×比例×倍率×时长 一节点输出）
│   └── limao-vram-tools/       # 狸猫自研显存治理节点包
│       ├── LimaoVRAMGuard      #   显存守卫（自动清理/告警）
│       ├── LimaoVAEChunkDecode #   分块解码（32帧分块）
│       └── LimaoPeakWatch      #   显存峰值监控
├── limao-app/                  # 实例服务三件套（开机全自动）
│   ├── autostart_v2.sh         #   开机自启入口（customer.cmd.sh → /etc/autodl.sh → 本脚本）
│   ├── gateway6006.py          #   6006 常驻反向代理网关（就绪前亮欢迎页，HTTP+WS 全穿透，零空窗）
│   └── panel6008.py            #   6008 狸猫专属进入面板（实时状态 + 一键进工作台）
├── limao-home/                 # Jupyter 起始页门户（狸猫AI·H3视频工坊）+ 使用说明
├── MODELS.md           # 模型依赖清单（文件名/目录/大小/来源/SHA256）
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
- **拿来就能用**：40 个正式工作流逐一实测校验，模型依赖齐备、开箱即跑

## 🚀 安装

```bash
# 1. 工作流：复制到 ComfyUI 工作流目录
cp -r workflows/狸猫* /path/to/ComfyUI/user/default/workflows/

# 2. 自研节点包 —— 两套都要装，缺一会报缺节点
cp -r custom_nodes/limao-h3-suite   /path/to/ComfyUI/custom_nodes/
cp -r custom_nodes/limao-vram-tools /path/to/ComfyUI/custom_nodes/
```

模型依赖清单（文件名 / 存放目录 / 实测大小 / 下载来源 / SHA256）见 **[MODELS.md](MODELS.md)**。核心 H3 线 8 个模型逐字节校验值已实测；其余依赖按 MODELS.md 的分类表检索。

### 环境基线

| 组件 | 要求 |
|---|---|
| ComfyUI | **≥ 0.45.0**（工作流含 H3 原生节点与模板体系，低版本缺节点定义） |
| ComfyUI 模板包 | ≥ 0.11.104 |
| GPU / 显存 | 见下方「显存要求」 |
| Python / torch | 实例基线：Python 3.11 + PyTorch 2.x + CUDA 12.x；其他组合未逐一实测 |

### 显存要求（实测数据）

全部规格在 RTX 4080S 32G（现役构建机）与 4090 48G 上实测验证：

| 场景 | 显存峰值 | 最低显卡 |
|---|---|---|
| H3 生图 16MP（4K 直出） | ~13.7GB（解码画布 fp32） | 24G 可跑，32G 无压力 |
| H3 视频 0.6MP · 15 秒全长 362 帧双采 | **31.9GB**（贴 32G 顶未爆） | 4090 48G 推荐 |
| H3 视频 2K（2240×1408）· ≤8 秒 | ~30GB | 4080S 32G 可行（2.5s 实测通过） |
| H3 视频 2K · 15 秒全长单段 | **35.4GB** | **4090 48G 级**（32G 必爆） |
| 80G+（H800/A100） | — | 全规格无顾虑，多任务并行 |

> ⚠️ **关键数字：整套工作流实测最高显存峰值 38.5GB**（TE 25.8G + VAE 动态分阶段，48G 卡贴顶未爆）。**发布镜像的最低显卡规格为 48G**——24G/32G 卡只能跑上表前两行以内的场景，直接开 2K 全长会 OOM。背靠背连跑第二部视频时建议先插一枚「狸猫·显存清扫」（LimaoH3MemorySweep）节点或间隔一分钟，42G 残留 + 16G 新请求会爆。

### 端口与访问（发布镜像）

| 端口 | 服务 | 说明 |
|---|---|---|
| **6006** | 狸猫网关（推荐入口） | 常驻反向代理，ComfyUI 就绪前亮欢迎页，HTTP+WS 全穿透零空窗 |
| 6008 | 狸猫专属进入面板 | 实时状态 + 一键进工作台 |
| 8188 | ComfyUI 主服务 | 直连用（一般无需直接访问） |

镜像发布时请开放以上三个端口；**用户从 6006 进入**即可。

### 开机自启链路

`/init/bin/customer.cmd.sh → /etc/autodl.sh → limao-app/autostart_v2.sh`，自启链路依次拉起：

1. 空闲自动关机看门狗（调 **`/root/autoshutdown_watchdog.sh`**）
2. 模型自举（调 **`/root/bootstrap_models.sh`**，幂等补缺模型）
3. ComfyUI 永驻 8188
4. 6006 常驻网关
5. 6008 进入面板

> ⚠️ **注意**：`autoshutdown_watchdog.sh` 与 `bootstrap_models.sh` **不在本仓库中**——由狸猫发布镜像的初始化脚本投放至 `/root/`。从本仓库独立部署时，这两步会被 `[ -f ]` 保护跳过（**不影响 ComfyUI 主链路**，只是少了空闲关机与模型自检），按需自行配置；使用狸猫官方发布镜像则开机全自动。

## 📄 许可与合规

### 狸猫专有许可

本项目采用 [狸猫专有许可](LICENSE)：

- ✅ **个人使用自由**：完整保留许可与全部狸猫数字指纹标识的前提下，个人创作与学习免费
- 🔑 **商用需授权码**：通过狸猫AI 正规渠道获得授权码（格式 `LM-XXXX-XXXX`）的用户可在授权范围内商用
- ⛔ **禁止去指纹再分发**：删除、修改、伪造或绕过任何狸猫数字指纹（JSON `extra.limao` 元数据、节点 `properties.limao_fp / limao_lic` 字段、工作流内版权声明节点）后的二次发布被明确禁止，发现即视为盗版

> 📌 **镜像广场发布条款**（仙宫云 / 优云等平台）：用户克隆狸猫发布镜像即视为"获得狸猫AI 授权使用"——个人免费、商用需 LM 授权码、禁止去指纹二次分发。此条款需在**镜像详情页**与工作流内声明节点（MarkdownNote）中保持可见。

### 第三方模型许可

| 模型 | 许可 | 合规要点 |
|---|---|---|
| **MiniMax H3-Image**（生图线主模型） | MiniMax Community License | 遵循其社区许可条款；注意其**地区限制条款**，受限地区用户不得使用 |
| H3 视频线（Comfy-Org/MiniMax-H3 官方重打包） | 随上游 MiniMax 许可 | 界面与镜像详情页需标注模型来源 `Comfy-Org/MiniMax-H3` |
| Wan / LTX / Qwen-Image / Flux 等其他开源模型 | 各自上游许可 | 见 MODELS.md 来源列，商用前请自查对应许可 |

镜像发布时请在界面与详情页**显著标注所含模型名称**，并核实 MiniMax Community License 的地区适用范围。

---

<div align="center">

**© 狸猫AI · H3视频工坊** · 狸猫出品，必属精品 🐾

</div>
