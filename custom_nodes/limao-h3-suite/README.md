# 狸猫AI · limao-h3-suite（H3 视频工坊自研节点套件）

> 版本 1.0.0 · 狸猫AI 出品
> 设计信条：**画质跟原版一致是底线，稳定与可守护是狸猫的增值。**

## 安装

```bash
cd ComfyUI/custom_nodes
git clone <本仓库> limao-h3-suite   # 或直接复制本目录
```

重启 ComfyUI，节点菜单出现「狸猫」分类即安装成功。零第三方依赖（仅 torch）。

## 节点一览

### 🛡 狸猫·模型哨兵（LimaoH3ModelSentinel）
采样前校验模型文件的存在性、SHA256 指纹与全盘同名异实体。
**这是 2026-11 光斑事故的直接产物**：latent 上采样器 fp16 文件被静默顶替，
画面满屏彩屑，排查一天一夜。挂上哨兵后此类事故在采样前就被拦截。

- 挂载：不接任何线，放画布任意位置即可
- 推荐：守护 latent 上采样器、主模型、关键 LoRA 三类文件
- 校验通过后把报告里的 SHA256 回填到 `expected_sha256`，实现逐字节钉死
- `on_mismatch=block` 时指纹异常直接终止运行（可切 warn 仅告警）

### 🖼 狸猫·图参考审计（LimaoH3RefImageAudit）
9 张参考图合规预检（官方约束）：短边 ≥256px、宽高比 0.4–2.5、
完全重复图检测。给出「正脸/侧脸/全身/服饰/风格」分工建议。

### 🎬 狸猫·视频参考审计（LimaoH3RefVideoAudit）
3 条参考视频合规预检：≥5 帧（否则官方节点直接报错）、单条 2–15s、
总时长 ≤15s 预算、配对音频提醒、以及「124 帧生成只取参考前段」的提醒。

### 🎵 狸猫·音频参考审计（LimaoH3RefAudioAudit）
3 条独立参考音频合规预检：单条 2–15s、总时长 ≤15s。

### 🌉 狸猫·帧桥（LimaoH3FrameBridge）
H3 生态帧张量存在 `[B,T,H,W,C]` / `[B,C,T,H,W]` 等多种五维布局，
多数后处理节点（RIFE/超分/导出）只吃 `[N,H,W,C]`。本节点自动识别
布局（通道维最少维优先启发式）并安全展开，是接入补帧/后处理的安全网。

### 🎲 狸猫·种子锻炉（LimaoH3SeedForge）
三模式种子供给，输出直连 `RandomNoise.noise_seed`：
- `fixed` 固定种子，结果可复现
- `random` 每跑随机（内部强制重算，不受 ComfyUI 缓存影响）
- `pool` 狸猫安全种子池轮换（内部实测干净种子）

### ⚡ 狸猫·显存守卫（LimaoH3VRAMGuard）
模型链 passthrough，`balanced`/`aggressive` 两档缓存治理，削峰防 OOM；
`off` 时零干预。

### 🧹 狸猫·显存清道夫（LimaoH3MemorySweep）
解码→保存之间的全量清理（RAM gc + VRAM cache/ipc + 可选模型卸载），
纯 passthrough 副作用节点。揉合自 16G 显存精修版的 RAMCleanup +
VRAMCleanup 双节点并收编为狸猫自研；低显存机型建议保持常驻激活，
清理发生在成片解码之后，不影响画质。

## 配套工作流

`workflows/狸猫·H3视频/狸猫·H3·九图三视频三音频·多参考专属.json`（v1.1.0 四合一）
——九图三视频三音频满配参考 + 双采放大 + bf16 上采样器钉死 +
全套审计哨兵 + 显存清道夫常驻，并揉合三档功能（bypass 待命一键切换）：
- **武戏档**：ExtendIntermediateSigmas 双阶段重采样（4 步·0.65→0.28·sine）
- **极致精修档**：sigma 精修 + JR 统一加速面板 + BUNNY V2 语义桥
- **多镜头一键档**：H3MultishotSampler 整链（`---` 分镜脚本、镜头链式衔接、接缝裁剪）
