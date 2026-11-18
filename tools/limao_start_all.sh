#!/bin/bash
# 狸猫一键拉起：ComfyUI(8188) + nginx欢迎层(6006) + 创作面板(6008)
export HF_ENDPOINT=https://hf-mirror.com
pgrep -f 'main.py --listen' >/dev/null || (cd /root/ComfyUI && nohup setsid /root/miniconda3/bin/python main.py --listen 0.0.0.0 --port 8188 > /root/comfy.log 2>&1 < /dev/null &)
sleep 2
pgrep -x nginx >/dev/null || nginx
pgrep -f 'limao_ui/app.py' >/dev/null || (cd /root/limao-ui && nohup setsid /root/miniconda3/bin/python app.py > /root/limao-ui/app.log 2>&1 < /dev/null &)
echo '狸猫服务已拉起：8188 后端 / 6006 欢迎层 / 6008 面板'
