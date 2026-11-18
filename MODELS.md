# 📦 模型依赖清单

> 口径：**40 个正式工作流**（存档目录不计）共引用 **175 个去重模型文件**。
> 狸猫**发布镜像已内置全部依赖**（平台共享库软链挂载，开机零下载）；从本仓库独立部署者按本清单逐个配置。
>
> 校验方法：`sha256sum <文件>` 与第一节数值比对；或安装 `custom_nodes/limao-h3-suite` 的 **LimaoH3ModelSentinel（模型哨兵）** 节点在工作流内自动校验存在性与一致性。

---

## 一、核心 H3 线必装清单（SHA256 实测）

### 生图线（狸猫·H3生图 · 4K 直出双工作流）

| 文件 | models 目录 | 实测大小 | 来源仓库 | SHA256 |
|---|---|---|---|---|
| `minimax_h3_image_pruned_int8_convrot.safetensors` | `diffusion_models/minimax/` | ~21 GB（INT8 剪枝） | H3 主模型源 smhfacct（4 选 1 定版 b25 系） | `83eb140f1ff95c068f8a6886e6d3f3d0d4ab2e07bb2fe6d2ef992a51146ee622` |
| `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | `text_encoders/` | 25.77 GB | Comfy-Org/MiniMax-H3（uncensored 供应链 linjian257） | `bc2ced0fbea64757fa9acddccfc0b3f4819d1dcf1da6c124d690d368be283923` |
| `qwen3vl_32b_minimax_h3_int4_convrot.safetensors` | `text_encoders/` | ~14 GB | Abiray/MiniMax-H3-GGUF（32G 系统盘适配版，画质损失可忽略） | `21fd2e2f06bc4fc422c6aa20893fe189edbbd9ab3068215f96e7a6cf2f6cb5bb` |
| `minimax_h3_image_vae_fp16.safetensors` | `vae/` | 1.1 GB | Comfy-Org/MiniMax-H3 | `d80e9c2e5cfc9844869961ff5a58c9a9e52182df6bfb30b26018dd7f348721af` |

> 实例适配注：`qwen3.5_9b_w4a8_gptq.safetensors`（PE 提示词扩写）在 32G 构建机上缺货，官方模板默认关闭 PE 不受影响；需要时以 `qwen3.5_4b_bf16` 替换。

### 视频线（狸猫·H3视频 旗舰 + 全部视频类工作流）

| 文件 | models 目录 | 实测大小 | 来源仓库 | SHA256 |
|---|---|---|---|---|
| `minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors` | `diffusion_models/minimax/` | **20.97 GB** | H3 主模型源 smhfacct（4 选 1 定版 b25） | `a629cfea8d89a071b140c6e1935dc9a23e72de6badc18975a2bb9e6d1423d76d` |
| `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | `text_encoders/` | **25.77 GB** | Comfy-Org/MiniMax-H3 | （同生图线） |
| `minimax_h3_video_vae_fp16.safetensors` | `vae/` | 4.9 GB | Comfy-Org/MiniMax-H3 | `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522` |
| `minimax_h3_audio_vae_fp32.safetensors` | `vae/` | 578 MB | Comfy-Org/MiniMax-H3 **官方重打包版**（勿用 MiniMax 原始格式，缺 encoder/decoder 键会静默失败） | `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48` |
| `H3_Combat_V2.safetensors` | `loras/minimax/` | 148 MB | JOKER141（武戏 LoRA） | `5b3edb09e9d6029439badf9bc9db4ba4a355ae679b0810888de82c4793c0bac8` |
| `minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors` | `loras/minimax/` | 592 MB | t8star（turbo 加速 LoRA 三件套之一） | `7098acf3ee75028fd9fcd948f50fcc8d995057fabb76f86bd3ca2c0ffc58e409` |
| `minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors` | `loras/minimax/` | 1.9 GB | t8star（REF2VA 8 步 turbo） | `6a56f41ab4229c9dd845b9501bbd475ee57e112d846cf2e819d534a1ae928c5a` |

---

## 二、全量依赖速查表（175 个去重文件）

按 ComfyUI `models/` 子目录分组（工作流字段名即 JSON 中的输入槽位，同名文件在多个工作流间共享）。
以下依赖均已内置狸猫发布镜像；独立部署时按文件名到来源渠道（HuggingFace / hf-mirror / ModelScope / liblib / 各作者仓库）检索。


#### `LLM/ (gguf)`（4 个）

| 文件名 | 工作流字段 |
|---|---|
| `Qwen3.6-35B-A3B-mmproj-BF16.gguf` | mmproj |
| `Qwen3.8-27B-Q4_K_M.gguf` | local_mmproj |
| `Qwen3.8-27B-mmproj-BF16.gguf` | local_context_size |
| `mmproj-BF16.gguf` | mmproj |

#### `audio_encoders/`（1 个）

| 文件名 | 工作流字段 |
|---|---|
| `wav2vec2-chinese-base_fp16.safetensors` | audio_encoder_name |

#### `detection/`（2 个）

| 文件名 | 工作流字段 |
|---|---|
| `dw-ll_ucoco_384_bs5.torchscript.pt` | pose_estimator |
| `yolox_l.torchscript.pt` | bbox_detector |

#### `diffusion_models/`（60 个）

| 文件名 | 工作流字段 |
|---|---|
| `Ditto/ditto_global_style_comfy.safetensors` | vace_model |
| `Ltx/ltx-2.3-22b-dev_transformer_only_fp8_scaled.safetensors` | unet_name |
| `Ltx/ltx-2.3-22b-distilled_transformer_only_fp8_input_scaled_v3.safetensors` | unet_name |
| `Ltx/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | unet_name |
| `MelRoFormer/MelBandRoformer_fp16.safetensors` | model_name |
| `MelRoFormer/MelBandRoformer_fp32.safetensors` | model_name |
| `MiniMaxH3_SemanticBridge_v1.safetensors` | model_name |
| `Qwen3.6-35B-A3B-UD-Q2_K_XL.gguf` | model |
| `Qwen3.8-27B-UD-Q4_K_M.gguf` | model |
| `Wan/Wan21-SkyReelsV3-A2V_fp8_scaled_mixed.safetensors` | unet_name |
| `Wan/Wan21_SteadyDancer_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors` | model |
| `Wan/Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors` | model |
| `Wan/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors` | model |
| `Wan/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors` | model |
| `Wan/wan2.1_14B_SCAIL_2_fp16.safetensors` | model_name |
| `Wan/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors` | model |
| `Wan/wan2.1_14B_SCAIL_2_int8_convrot.safetensors` | model |
| `Wan/wan2.1_14B_SCAIL_2_nvfp4_comfy_V2.safetensors` | model |
| `Wan/wan2.1_t2v_14B_fp16.safetensors` | model |
| `Wan/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | unet_name |
| `Wan/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | unet_name |
| `Wan21_Uni3C_controlnet_fp16.safetensors` | model |
| `Wan2_1_VAE_bf16.safetensors` | model_name |
| `Wan2_1_VAE_fp32.safetensors` | model_name |
| `face_yolov8n.pt` | model_name |
| `flux/Flux2-Klein-9B-True-v2-fp8mixed.safetensors` | unet_name |
| `gimmvfi_r_arb_lpips_fp32.safetensors` | model |
| `ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors` | model_name |
| `ltx-2.3-spatial-upscaler-x2-1.0.safetensors` | model_name |
| `ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | model_name |
| `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | model_name |
| `ltx-av-step-1751000_vocoder_24K.safetensors` | ckpt_name |
| `minimax/minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors` | unet_name |
| `minimax/minimax_h3_ref2va_int8_convrot.safetensors` | unet_name |
| `minimax_h3_latent_upscaler_3d_fp16.safetensors` | model_name |
| `person_detect_v0_l.pt` | model_name |
| `person_detect_v0_l_yv11.pt` | model_name |
| `qwen/qwen_image_2.1_bf16.safetensors` | unet_name |
| `qwen/qwen_image_2.1_turbo_int8_convrot.safetensors` | unet_name |
| `qwen/qwen_image_edit_2511_fp8mixed.safetensors` | unet_name |
| `qwen_image_edit_2511_fp8_e4m3fn.safetensors` | ckpt_name |
| `rife47.pth` | ckpt_name |
| `rife49.pth` | ckpt_name |
| `sam3.1_multiplex_fp16.safetensors` | ckpt_name |
| `sam3.safetensors` | model |
| `sdpose_wholebody_fp16.safetensors` | ckpt_name |
| `umt5-xxl-enc-bf16.safetensors` | model_name |
| `umt5-xxl-enc-fp8_e4m3fn.safetensors` | model_name |
| `wan22RemixT2VI2V_i2vHighV30.safetensors` | unet_name |
| `wan22RemixT2VI2V_i2vLowV30.safetensors` | unet_name |
| `wan_2.1_vae.safetensors` | model_name |
| `yolo11x-pose.pt` | model_name |
| `yolo11x.pt` | model_name |

#### `loras/`（60 个）

| 文件名 | 工作流字段 |
|---|---|
| `Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors` | lora |
| `Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank256_bf16.safetensors` | lora_1 |
| `Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | lora |
| `Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank128_bf16.safetensors` | lora |
| `Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors` | lora |
| `Ltx/ltx-2.3-22b-distilled-lora-384.safetensors` | lora_name |
| `Ltx/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors` | lora_name |
| `Motion_Repair_V2.safetensors` | lora_name |
| `Qwen/Kook_Qwen_V3极致真实.safetensors` | lora_name |
| `Qwen/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` | lora_name |
| `Qwen/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors` | lora_name |
| `Qwen/Qwen-Image-Edit-F2P.safetensors` | lora_name |
| `Qwen/next-scene_lora-v2-3000.safetensors` | lora_name |
| `Qwen/qwen-image-edit-2511-multiple-angles-lora.safetensors` | lora_name |
| `Wan/FastWan_T2V_14B_480p_lora_rank_128_bf16.safetensors` | lora_2 |
| `Wan/SVI_v2_PRO_Wan2.2-I2V-A14B_HIGH_lora_rank_128_fp16.safetensors` | lora_name |
| `Wan/SVI_v2_PRO_Wan2.2-I2V-A14B_LOW_lora_rank_128_fp16.safetensors` | lora_name |
| `Wan/Scail-2_Remix_LoRA_non_Relighting_rank256.safetensors` | lora |
| `Wan/Scail-2_relighting-lora.safetensors` | lora_0 |
| `Wan/Wan2.1-Fun-14B-InP-HPS2.1.safetensors` | lora_2 |
| `Wan/Wan2.1-Fun-14B-InP-HPS2.1_reward_lora_comfy.safetensors` | lora |
| `Wan/Wan2.2-Fun-A14B-InP-HIGH-HPS2.1_resized_dynamic_avg_rank_14_bf16.safetensors` | lora_3 |
| `Wan/Wan2.2-Fun-A14B-InP-LOW-HPS2.1_resized_dynamic_avg_rank_15_bf16.safetensors` | lora_4 |
| `Wan/Wan2.2-Fun-A14B-InP-high-noise-MPS.safetensors` | lora_name |
| `Wan/Wan2.2-Fun-A14B-InP-low-noise-HPS2.1.safetensors` | lora_4 |
| `Wan/Wan2.2-I2V-Slop-Bounce-Low-i2v.safetensors` | lora_3 |
| `Wan/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors` | lora_1 |
| `Wan/Wan2.2-MI2V-A14B-backbone_high_noise.safetensors` | lora |
| `Wan/Wan2.2-MI2V-A14B-backbone_low_noise.safetensors` | lora |
| `Wan/Wan21-PusaV1-LoRA-14B-rank512-bf16.safetensors` | lora_2 |
| `Wan/Wan21_I2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors` | lora |
| `Wan/WanAnimate_relight_lora_fp16.safetensors` | lora_0 |
| `Wan/Wan_2_1_T2V_14B_rCM_lora_average_rank_83_bf16.safetensors` | lora |
| `Wan/wan-m4crom4sti4-i2v-106epo-k3nk.safetensors` | lora |
| `Wan/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors` | lora_2 |
| `Wan/wan2.1_i2v_lora_rank64_lightx2v_4step.safetensors` | lora_1 |
| `Wan/wan2.2_i2v_A14b_high_noise_lora_rank64_lightx2v_4step_1022.safetensors` | lora_name |
| `Wan/wan2.2_i2v_A14b_low_noise_lora_rank64_lightx2v_4step_1022.safetensors` | lora_name |
| `Wan/wan2.2_t2v_A14b_high_noise_lora_rank64_lightx2v_4step_1217.safetensors` | lora_0 |
| `Wan/wan2.2_t2v_A14b_low_noise_lora_rank64_lightx2v_4step_1217.safetensors` | lora_0 |
| `animate/Q弹3.safetensors` | lora_0 |
| `flux-2-klein-9b-360-panorama-lora.safetensors` | lora_name |
| `lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank16_bf16.safetensors` | lora_name |
| `minimax/H3_Combat_V2.safetensors` | lora_name |
| `minimax/H3_speed_slider_1.1.safetensors` | lora_name |
| `minimax/Motion_Repair_V2.safetensors` | lora_name |
| `minimax/MysticXXX_MMH3-V4.safetensors` | lora_name |
| `minimax/minimax_h3_character_swap_v1.1_ref2va_fro.safetensors` | lora_name |
| `minimax/minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors` | lora_name |
| `minimax/minimax_h3_turbo_4step_10ErosMax_test4_pruned_curveproj1025_exp_v001-T8.safetensors` | lora_name |
| `minimax/minimax_h3_turbo_v4_step600_ema_DasiwaREF2VAHybridV1_0_curveproj1025_compat_v001.safetensors` | lora_name |
| `minimax/minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors` | lora_name |
| `minimax/viggle_animate_dmd_lora.safetensors` | lora_name |
| `minimax/电影感H3-loraV1.0正式版.safetensors` | lora_name |
| `minimax_h3_dmd_ref2va_8step_turbo_pruned.safetensors` | lora_name |
| `qwen/Qwen2.1_一致性无偏移_GH_V1.0.safetensors` | lora |
| `qwen/Qwen2.1_万物移除Remove_GH.safetensors` | lora_name |
| `qwen/Qwen2.1_扩图_GH_3750.safetensors` | lora_name |
| `qwen/Qwen21-换头bfs_head_v1.1_qwen_2.1.safetensors` | lora |
| `qwen/Qwen21-换身bfs_body_swap_v1.0_qwen_2.1.safetensors` | lora |

#### `models 其他/`（21 个）

| 文件名 | 工作流字段 |
|---|---|
| `Ltx/ltx-2-19b-distilled-lora-384.safetensors` | name |
| `Qwen-Image-2.1-PE-I2I.Q5_K_S.gguf` | 图生图模型 |
| `Qwen-Image-2.1-PE-I2I.mmproj-bf16.gguf` | 视觉模型 |
| `Qwen-Image-2.1-PE-T2I.Q5_K_S.gguf` | 文生图模型 |
| `Qwen/Qwen-Image-Lightning-4steps-V1.0.safetensors` | name |
| `Wan/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors` | name |
| `Wan/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` | name |
| `Wan2_1-InfiniTetalk-Single_fp16.safetensors` | name |
| `WanAnimate_relight_lora_fp16.safetensors` | name |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | name |
| `ltx-2-spatial-upscaler-x2-1.0.safetensors` | name |
| `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | name |
| `ltx-2.5-audio-vae-bf16.safetensors` | name |
| `ltx-2.5-video-vae-bf16.safetensors` | name |
| `minimax_h3_image_pruned_int8_convrot.safetensors` | name |
| `minimax_h3_image_vae_fp16.safetensors` | name |
| `qwen/qwen_image_edit_2511_bf16.safetensors` | name |
| `qwen_image_2.1_int8_convrot.safetensors` | name |
| `qwen_image_2.1_turbo_int8_convrot.safetensors` | name |
| `qwen_image_2.1_vae_bf16.safetensors` | name |
| `qwen_image_vae.safetensors` | name |

#### `text_encoders/`（19 个）

| 文件名 | 工作流字段 |
|---|---|
| `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | clip_name |
| `clip_vision_h.safetensors` | clip_name |
| `clip_vision_vit_h.safetensors` | clip_name |
| `fixed_embed_fwd_anyframe.safetensors` | text_cond |
| `gemma-3-12b-it-qat-q4_0-unquantized_readout_proj/model/model.safetensors` | gemma_path |
| `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | clip_name |
| `gemma_3_12B_it.safetensors` | clip_name1 |
| `gemma_3_12B_it_fp8_e4m3fn.safetensors` | clip_name1 |
| `ltx-2.3_text_projection_bf16.safetensors` | clip_name2 |
| `qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors` | clip_name |
| `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors` | clip_name |
| `qwen3.5_9b_w4a8_gptq.safetensors` | clip_name |
| `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | clip_name |
| `qwen3vl_8b_bf16.safetensors` | clip_name |
| `qwen3vl_8b_int8_convrot.safetensors` | clip_name |
| `qwen_2.5_vl_7b.safetensors` | clip_name |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | clip_name |
| `qwen_3_8b_fp8mixed.safetensors` | clip_name |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | clip_name |

#### `vae/`（8 个）

| 文件名 | 工作流字段 |
|---|---|
| `LTX23_audio_vae_bf16.safetensors` | vae_name |
| `LTX23_video_vae_bf16.safetensors` | vae_name |
| `flux2-vae.safetensors` | vae_name |
| `minimax_h3_audio_vae_fp32.safetensors` | vae_name |
| `minimax_h3_video_vae_fp16.safetensors` | vae_name |
| `minimax_h3_video_vae_int8_convrot.safetensors` | vae_name |
| `taeh3.safetensors` | tiny_vae |
| `taeltx2_3.safetensors` | vae_name |

---

## 三、来源仓库索引（狸猫供应链实勘）

| 来源 | 内容 |
|---|---|
| `Comfy-Org/MiniMax-H3`（HuggingFace 官方重打包） | H3 视频/音频 VAE、qwen3vl 系编码器 |
| `Abiray/MiniMax-H3-GGUF` | int4/int8 convrot 量化版编码器 |
| smhfacct | H3 主模型（4 选 1，定版 b25 系） |
| linjian257 | qwen3vl uncensored 供应链 |
| t8star | turbo LoRA×3、taeh3（Taeh3-Comfy）、SemanticBridge×2（T8_Compat） |
| JOKER141 | Combat_V2、Motion_Repair_V2 |
| RunningHubAI | speed_slider、Kook×2 |
| kirk86413 | 电影感 CinematicMH3-V01 |
| KENIC-1 | upscaler |
| unsloth | Qwen3.8-27B UD-Q4_K_M（16.46GB）+ mmproj-BF16（0.93GB） |
| ModelScope `Comfy-Org/MOSS-Image` | MOSS 线：moss_image_sft_int8_convrot（5.04GB）+ qwen3.5_9b_int8_convrot（9.75GB）+ flux2-vae（336MB） |
| 狸猫实例共享库（`/.autodl/`） | 发布镜像将上述全部依赖软链挂载，开机零下载 |

> 国内下载渠道：HuggingFace 镜像 `hf-mirror.com`（audio VAE 等小文件实测可用）、ModelScope。

---

## 四、部署说明

- **狸猫发布镜像（推荐）**：全部模型内置，开机 `bootstrap_models.sh` 幂等自检补缺，用户无感。
- **独立部署**：
  1. 先装第一节核心 8 件（H3 生图 + 视频线即可跑通主打全部能力）；
  2. 再按第二节全量表补齐你用到的工作流对应的分类文件；
  3. 文件落位后用模型哨兵节点或 `sha256sum` 校验；
  4. 显存与显卡要求见 README「显存要求」节。
