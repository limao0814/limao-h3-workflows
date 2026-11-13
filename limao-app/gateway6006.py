#!/usr/bin/env python3
# 狸猫常驻网关(6006)：秒绑端口，ComfyUI(8188)就绪前亮狸猫欢迎页，就绪后透明反向代理(HTTP+WebSocket)
# 革命点：不再杀进程切换端口，开机到就绪全程 6006 永不拒连（狸猫原创）
import asyncio, pathlib, zlib
from aiohttp import web, ClientSession, ClientTimeout, WSMsgType

BACKEND = 'http://127.0.0.1:8188'
HOP = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
       'te', 'trailers', 'transfer-encoding', 'upgrade', 'host',
       'sec-websocket-key', 'sec-websocket-version', 'sec-websocket-protocol',
       'sec-websocket-extensions', 'sec-websocket-accept'}

SPLASH = pathlib.Path('/root/开始.html').read_text('utf-8')
INJ = ('<div id="limao-boot" style="position:fixed;top:0;left:0;right:0;z-index:99999;'
       'background:linear-gradient(90deg,#ff6b35,#d4af37);color:#0a0e1a;'
       'font:600 14px/1.4 system-ui;padding:10px 16px;text-align:center">'
       '&#9203; ComfyUI &#27491;&#22312;&#21551;&#21160;&#65292;&#23601;&#32490;&#21518;&#33258;&#21160;&#36827;&#20837;&#24037;&#20316;&#21488;&#8230;</div>'
       '<script>(function(){function p(){fetch("/_limao_status").then(function(r){return r.json()})'
       '.then(function(d){if(d.ready){document.getElementById("limao-boot").innerHTML='
       '"&#9989; &#21551;&#21160;&#23436;&#25104;&#65292;&#27491;&#22312;&#36827;&#20837;&#24037;&#20316;&#21488;&#8230;";'
       'setTimeout(function(){location.reload()},1200)}else{setTimeout(p,3000)}})'
       '.catch(function(){setTimeout(p,3000)})})();p()})()</script>')
SPLASH = SPLASH.replace('</body>', INJ + '</body>')

MAIN_WF = pathlib.Path('/root/limao-app/狸猫·H3·全域参考锻造·从零版.json')
# 新设备无工作流历史时，自动加载狸猫主打工作流（老用户会话不受影响）
AUTOLOAD = ('<script>(function(){function ok(){return !localStorage.getItem("Comfy.Workflow.LastOpenPaths")}'
            'function go(){if(!window.app){return setTimeout(go,300)}'
            'if(!ok()){return}'
            'setTimeout(function(){try{var g=app.rootGraph||app.graph;'
            'var c=g&&g._nodes?g._nodes.length:99;'
            'if(c<=14){fetch("/limao_main_workflow").then(function(r){return r.json()})'
            '.then(function(w){return app.loadGraphData(w)}).catch(function(){})}}catch(e){}},2500)}'
            'go()})()</script>')

async def _healthy(client):
    try:
        async with client.get(BACKEND + '/system_stats',
                              timeout=ClientTimeout(total=2)) as r:
            return r.status == 200
    except Exception:
        return False

async def ws_proxy(req, client):
    burl = BACKEND + req.rel_url.path_qs
    ws_out = web.WebSocketResponse(autoping=True)
    await ws_out.prepare(req)
    try:
        async with client.ws_connect(burl, timeout=ClientTimeout(total=15, sock_read=None)) as ws_in:
            async def pump(src, dst):
                async for msg in src:
                    if msg.type == WSMsgType.TEXT:
                        await dst.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await dst.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
            t1 = asyncio.create_task(pump(ws_in, ws_out))
            t2 = asyncio.create_task(pump(ws_out, ws_in))
            done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except Exception:
        pass
    return ws_out

COMPRESSIBLE = ('application/json', 'text/html', 'text/css', 'text/javascript',
                'application/javascript', 'image/svg+xml')

async def _warmup(client):
    # 开机后首次 /object_info 生成要 ~10s，提前预热让用户首次进界面秒开
    try:
        await client.get(BACKEND + '/object_info', timeout=ClientTimeout(total=120))
    except Exception:
        pass

async def handler(req):
    if req.path == '/limao_cover.png':
        return web.FileResponse('/root/limao_cover.png')
    if req.path == '/limao_main_workflow':
        return web.FileResponse(MAIN_WF, headers={'Cache-Control': 'no-store'})
    client = req.app['client']
    if not req.app['ready']:
        if await _healthy(client):
            req.app['ready'] = True
            asyncio.get_event_loop().create_task(_warmup(client))
        elif req.path == '/_limao_status':
            return web.json_response({'ready': False})
        else:
            return web.Response(text=SPLASH, content_type='text/html', charset='utf-8')
    if req.path == '/_limao_status':
        return web.json_response({'ready': True})
    if req.headers.get('Upgrade', '').lower() == 'websocket':
        return await ws_proxy(req, client)
    url = BACKEND + req.rel_url.raw_path_qs  # 用原始编码路径：aiohttp 解码会把 %2F 变成 /，导致 userdata 嵌套路径 404
    headers = {k: v for k, v in req.headers.items()
               if k.lower() not in HOP and k.lower() != 'origin'}
    # 剥离Origin：新版ComfyUI安全中间件对Origin与host不一致的请求返回403,
    # 而前端ES module脚本天生带Origin——同源部署下后端不需要该头,剥离即全通
    body = req.content if req.can_read_body else None
    try:
        async with client.request(req.method, url, headers=headers, data=body,
                                  allow_redirects=False,
                                  timeout=ClientTimeout(total=None, sock_connect=5)) as up:
            rh = {}
            for k, v in up.headers.items():
                lk = k.lower()
                if lk in HOP or lk == 'content-length':
                    continue
                if lk == 'location' and v.startswith(BACKEND):
                    v = v[len(BACKEND):] or '/'
                rh[k] = v
            # gzip 透明压缩：/object_info 等 27MB 大JSON → ~2.8MB，外链进界面提速约10倍
            can_gz = ('gzip' in req.headers.get('Accept-Encoding', '')
                      and up.status == 200
                      and any(up.headers.get('Content-Type', '').startswith(c) for c in COMPRESSIBLE)
                      and 'gzip' not in up.headers.get('Content-Encoding', '').lower())
            if can_gz:
                rh['Content-Encoding'] = 'gzip'
                rh['Vary'] = 'Accept-Encoding'
            # 首页HTML注入自动加载脚本：需整体缓冲后改写
            inject = (req.path in ('/', '/index.html') and up.status == 200
                      and up.headers.get('Content-Type', '').startswith('text/html'))
            if inject or can_gz:
                data = await up.read()
                if inject:
                    data = data.replace(b'</body>', AUTOLOAD.encode('utf-8') + b'</body>', 1)
                if can_gz:
                    co = zlib.compressobj(6, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
                    data = co.compress(data) + co.flush()
                rh['Content-Length'] = str(len(data))
                resp = web.StreamResponse(status=up.status, headers=rh)
                await resp.prepare(req)
                await resp.write(data)
            else:
                resp = web.StreamResponse(status=up.status, headers=rh)
                await resp.prepare(req)
                async for chunk in up.content.iter_any():
                    await resp.write(chunk)
            await resp.write_eof()
            return resp
    except Exception:
        req.app['ready'] = False
        return web.Response(text=SPLASH, content_type='text/html', charset='utf-8')

async def main():
    app = web.Application()
    app['ready'] = False
    app['client'] = ClientSession()
    app.router.add_route('*', '/{tail:.*}', handler)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 6006).start()
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
