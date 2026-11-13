#!/usr/bin/env python3
# 狸猫常驻网关(6006)：秒绑端口，ComfyUI(8188)就绪前亮狸猫欢迎页，就绪后透明反向代理(HTTP+WebSocket)
# 革命点：不再杀进程切换端口，开机到就绪全程 6006 永不拒连（狸猫原创）
import asyncio, pathlib
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

async def handler(req):
    if req.path == '/limao_cover.png':
        return web.FileResponse('/root/limao_cover.png')
    client = req.app['client']
    if not req.app['ready']:
        if await _healthy(client):
            req.app['ready'] = True
        elif req.path == '/_limao_status':
            return web.json_response({'ready': False})
        else:
            return web.Response(text=SPLASH, content_type='text/html', charset='utf-8')
    if req.path == '/_limao_status':
        return web.json_response({'ready': True})
    if req.headers.get('Upgrade', '').lower() == 'websocket':
        return await ws_proxy(req, client)
    url = BACKEND + req.rel_url.path_qs
    headers = {k: v for k, v in req.headers.items() if k.lower() not in HOP}
    body = req.content if req.can_read_body else None
    try:
        async with client.request(req.method, url, headers=headers, data=body,
                                  allow_redirects=False,
                                  timeout=ClientTimeout(total=None, sock_connect=5)) as up:
            rh = {}
            for k, v in up.headers.items():
                lk = k.lower()
                if lk in HOP:
                    continue
                if lk == 'location' and v.startswith(BACKEND):
                    v = v[len(BACKEND):] or '/'
                rh[k] = v
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
