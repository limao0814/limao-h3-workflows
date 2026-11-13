#!/bin/bash
# ============================================================
# 狸猫 ComfyUI 一键自启 v2（狸猫原创）
# 开机链路：/init/bin/customer.cmd.sh → /etc/autodl.sh → 本脚本
# 架构 v2：ComfyUI 永驻 8188；6006=常驻反向代理网关(就绪前亮欢迎页,无空窗)；
#          6008=狸猫专属进入面板。彻底废除 splash→takeover 杀进程切换。
# 可重入：已在跑则跳过，绝不互杀。
# ============================================================
export PATH="/usr/local/bin:/root/miniconda3/bin:$PATH"
LOG=/root/limao-autostart.log
echo "[$(date '+%F %T')] limao autostart v2 begin" >> $LOG

# 1) 空闲自动关机看门狗（总开关 /root/.autoshutdown_disable；阈值 /root/.autoshutdown_minutes）
if [ -f /root/autoshutdown_watchdog.sh ] && [ ! -f /root/.autoshutdown_disable ]; then
  if ! pgrep -f autoshutdown_watchdog.sh > /dev/null; then
    setsid nohup bash /root/autoshutdown_watchdog.sh < /dev/null > /dev/null 2>&1 &
    echo "[$(date '+%F %T')] watchdog launched" >> $LOG
  fi
fi

# 2) 模型自举（幂等：缺哪个下哪个）
if [ -f /root/bootstrap_models.sh ]; then
  if ! pgrep -f bootstrap_models.sh > /dev/null; then
    setsid nohup bash /root/bootstrap_models.sh < /dev/null > /dev/null 2>&1 &
    echo "[$(date '+%F %T')] bootstrap launched" >> $LOG
  fi
fi

# 3) ComfyUI 永驻 8188
if ! pgrep -f 'main.py --port 8188' > /dev/null; then
  export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
  cd /root/ComfyUI
  setsid nohup /root/miniconda3/bin/python main.py --port 8188 --listen 0.0.0.0 < /dev/null > /root/comfyui.log 2>&1 &
  echo "[$(date '+%F %T')] comfyui(8188) launched" >> $LOG
fi

# 4) 6006 常驻网关（秒绑，无空窗）
if ! pgrep -f 'limao-app/gateway6006.py' > /dev/null; then
  setsid nohup /root/miniconda3/bin/python /root/limao-app/gateway6006.py < /dev/null > /root/limao-gateway.log 2>&1 &
  echo "[$(date '+%F %T')] gateway6006 launched" >> $LOG
fi

# 5) 6008 狸猫专属进入面板
if ! pgrep -f 'limao-app/panel6008.py' > /dev/null; then
  setsid nohup /root/miniconda3/bin/python /root/limao-app/panel6008.py < /dev/null > /root/limao-panel.log 2>&1 &
  echo "[$(date '+%F %T')] panel6008 launched" >> $LOG
fi
