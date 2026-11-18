#!/bin/bash
# ComfyUI 启动脚本
# 当前版本为2025.11.4版本
# 您可以在终端输入bash /root/start-comfyui.sh来启动comfyUI
# 设置环境变量
export HF_ENDPOINT=https://hf-mirror.com
export PATH="/usr/local/bin:/root/miniconda3/bin:$PATH"

# 进入 ComfyUI 目录
cd /root/ComfyUI

# 启动 ComfyUI
/root/miniconda3/bin/python main.py --port 6006 --listen 127.0.0.1

