# -*- coding: utf-8 -*-
"""狸猫AI · H3 视频工坊 自研节点套件 —— 见 nodes.py 模块文档。"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__version__ = "1.0.0"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

# 注：本节点包为纯后端节点，无前端 JS 扩展，故不声明 WEB_DIRECTORY。
# （此前误声明 "./js" 而目录不存在，ComfyUI 启动日志会报 web 目录警告，已移除。）
