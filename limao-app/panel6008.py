#!/usr/bin/env python3
# 狸猫专属进入面板(6008)：品牌落地页 + 实时状态 + 一键进入工作台（狸猫原创）
import os, pathlib, json, asyncio
from aiohttp import web, ClientSession, ClientTimeout

BACKEND = 'http://127.0.0.1:8188'
COVER = pathlib.Path('/root/limao_cover.png').read_bytes()

PAGE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>狸猫AI · H3视频工坊 · 进入面板</title>
<style>
:root{--bg:#0a0e1a;--card:#151d30;--line:#243049;--gold:#d4af37;--fire:#ff6b35;
--txt:#e8ecf4;--sub:#9aa7bd;--grad:linear-gradient(135deg,#ff6b35,#d4af37);}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Noto Sans SC',system-ui,'PingFang SC','Microsoft YaHei',sans-serif;
background:radial-gradient(1200px 600px at 50% -10%,rgba(255,107,53,.12),transparent),var(--bg);
color:var(--txt);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.card{max-width:640px;width:100%;background:var(--card);border:1px solid var(--line);
border-radius:24px;overflow:hidden;box-shadow:0 30px 80px rgba(255,107,53,.18)}
.hero{position:relative}
.hero img{width:100%;display:block;aspect-ratio:16/7;object-fit:cover}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(transparent 40%,var(--card) 96%)}
.brand{position:absolute;left:0;right:0;bottom:14px;text-align:center;z-index:2}
.brand h1{font-size:34px;font-weight:900;letter-spacing:3px;background:var(--grad);
-webkit-background-clip:text;background-clip:text;color:transparent}
.brand p{color:var(--sub);font-size:13px;letter-spacing:6px;margin-top:4px}
.body{padding:28px 32px 34px}
.status{display:flex;align-items:center;gap:12px;background:rgba(212,175,55,.07);
border:1px solid rgba(212,175,55,.25);border-radius:16px;padding:14px 18px;margin-bottom:22px}
.dot{width:12px;height:12px;border-radius:50%;background:#64748b;flex:none;transition:.3s}
.dot.on{background:#22c55e;box-shadow:0 0 12px rgba(34,197,94,.7)}
.status b{font-size:15px}
.status span{color:var(--sub);font-size:13px;margin-left:auto;text-align:right}
.enter{display:block;width:100%;padding:18px;border:none;border-radius:16px;cursor:pointer;
background:var(--grad);color:#0a0e1a;font-size:19px;font-weight:900;letter-spacing:4px;
transition:.25s;box-shadow:0 10px 30px rgba(255,107,53,.35)}
.enter:hover{transform:translateY(-2px);box-shadow:0 16px 40px rgba(255,107,53,.5)}
.enter:disabled{filter:grayscale(.9);cursor:not-allowed;box-shadow:none}
.tip{color:var(--sub);font-size:12.5px;line-height:1.8;margin-top:16px;text-align:center}
.tip code{color:var(--gold);background:rgba(212,175,55,.12);padding:1px 7px;border-radius:6px}
.meta{display:flex;justify-content:center;gap:18px;margin-top:20px;color:#64748b;font-size:12px}
.seal{display:inline-flex;align-items:center;gap:8px;color:var(--gold);font-size:12.5px;
border:1px solid rgba(212,175,55,.35);border-radius:999px;padding:5px 14px}
</style>
</head>
<body>
<div class="card">
  <div class="hero">
    <img src="/limao_cover.png" alt="狸猫AI">
    <div class="brand"><h1>狸猫AI · H3视频工坊</h1><p>H3 VIDEO STUDIO</p></div>
  </div>
  <div class="body">
    <div class="status"><div class="dot" id="dot"></div><b id="st">检测中…</b><span id="st2"></span></div>
    <button class="enter" id="btn" onclick="go()" disabled>&#128274; 进 入 工 作 台</button>
    <p class="tip">点击按钮直达 ComfyUI 工作台（6006 端口）<br>
    若浏览器拦截跳转，请回到 AutoDL 控制台点击 <code>web6006</code> 自定义服务入口</p>
    <div class="meta"><span class="seal">🐾 狸猫专研</span><span id="ver"></span><span id="gpu"></span></div>
  </div>
</div>
<script>
var url=__GO_URL__;
function go(){window.open(url,'_blank')}
function poll(){fetch('/api/status').then(r=>r.json()).then(d=>{
  var dot=document.getElementById('dot'),st=document.getElementById('st'),
      st2=document.getElementById('st2'),btn=document.getElementById('btn');
  if(d.ready){dot.classList.add('on');st.textContent='ComfyUI 已就绪';
    st2.textContent='随时可以开工';btn.disabled=false;
    document.getElementById('ver').textContent='v'+(d.version||'');
    document.getElementById('gpu').textContent=d.gpu||'';}
  else{st.textContent='ComfyUI 启动中…';st2.textContent='就绪后按钮自动点亮';
    btn.disabled=true;setTimeout(poll,3000);}
}).catch(function(){setTimeout(poll,3000)})}
poll();
</script>
</body>
</html>'''

async def index(req):
    go_url = os.environ.get('AutoDLService6006URL') or 'http://127.0.0.1:6006'
    return web.Response(text=PAGE.replace('__GO_URL__', json.dumps(go_url)),
                        content_type='text/html', charset='utf-8')

async def cover(req):
    return web.Response(body=COVER, content_type='image/png')

async def status(req):
    try:
        async with req.app['client'].get(BACKEND + '/system_stats',
                                         timeout=ClientTimeout(total=2)) as r:
            d = await r.json()
            dev = (d.get('devices') or [{}])[0]
            return web.json_response({
                'ready': True,
                'version': d.get('system', {}).get('comfyui_version', ''),
                'gpu': (dev.get('name') or '').replace('NVIDIA ', ''),
                'vram_total': dev.get('vram_total'), 'vram_free': dev.get('vram_free')})
    except Exception:
        return web.json_response({'ready': False})

async def main():
    app = web.Application()
    app['client'] = ClientSession()
    app.router.add_get('/', index)
    app.router.add_get('/limao_cover.png', cover)
    app.router.add_get('/api/status', status)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 6008).start()
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
