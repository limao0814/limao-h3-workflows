# -*- coding: utf-8 -*-
"""狸猫H3工作流 · 创作台 UI（6008端口）
不进 ComfyUI 连线界面，直接表单化跑狸猫生图工作流。
后端调 run_t2i.py / run_edit.py（走 127.0.0.1:6006 ComfyUI API）。
用法: /root/miniconda3/bin/python /root/limao-ui/app.py  (监听 0.0.0.0:6008)
"""
import json, os, re, subprocess, threading, time, uuid
from flask import Flask, request, jsonify, send_from_directory

BASE = "http://127.0.0.1:8188"
PY = "/root/miniconda3/bin/python"
INPUT_DIR = "/root/ComfyUI/input"
OUTPUT_DIR = "/root/ComfyUI/output"
T2I_WF = "狸猫·H3生图/狸猫·H3生图·4K直出·文生图.json"
EDIT_WF = "狸猫·H3生图/狸猫·H3生图·4K直出·图像编辑.json"
RATIOS = ["16:9", "3:2", "1:1", "4:3", "2:3", "9:16"]

app = Flask(__name__)
TASKS = {}          # id -> {state, log, images, cmd, t0}
GPU_LOCK = threading.Lock()

HTML = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>狸猫H3工作流 · 创作台</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--line:#262b36;--txt:#e8eaf0;--sub:#9aa3b2;--acc:#ff8a3d;--ok:#4cc38a;--err:#e5534b}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;min-height:100vh}
.wrap{max-width:860px;margin:0 auto;padding:28px 20px 80px}
header{display:flex;align-items:baseline;gap:12px;margin-bottom:6px}
h1{font-size:22px;letter-spacing:.5px}
h1 .h3{color:var(--acc)}
.sub{color:var(--sub);font-size:13px;margin-bottom:22px}
.tabs{display:flex;gap:8px;margin-bottom:16px}
.tab{padding:9px 22px;border:1px solid var(--line);border-radius:10px;cursor:pointer;color:var(--sub);background:var(--card);font-size:14px}
.tab.on{color:var(--txt);border-color:var(--acc);background:rgba(255,138,61,.08)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:14px}
label{display:block;font-size:13px;color:var(--sub);margin:12px 0 6px}
textarea,input[type=text],input[type=number],select{width:100%;background:#0d0f13;border:1px solid var(--line);border-radius:9px;color:var(--txt);padding:10px 12px;font:14px/1.5 inherit}
textarea{min-height:96px;resize:vertical}
input[type=file]{color:var(--sub)}
.row{display:flex;gap:12px}
.row>*{flex:1}
.go{width:100%;margin-top:16px;padding:12px;border:0;border-radius:10px;background:var(--acc);color:#17110c;font-size:15px;font-weight:700;cursor:pointer}
.go:disabled{opacity:.5;cursor:not-allowed}
.hint{font-size:12px;color:var(--sub);margin-top:6px}
#log{background:#0a0c10;border:1px solid var(--line);border-radius:9px;padding:10px;font:12px/1.5 ui-monospace,Consolas,monospace;color:var(--sub);max-height:170px;overflow-y:auto;white-space:pre-wrap;display:none;margin-top:14px}
#state{display:none;margin-top:14px;padding:10px 14px;border-radius:9px;font-size:14px}
#state.run{background:rgba(255,138,61,.1);color:var(--acc)}
#state.ok{background:rgba(76,195,138,.12);color:var(--ok)}
#state.err{background:rgba(229,83,75,.12);color:var(--err)}
#imgs{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}
#imgs img{width:100%;border-radius:10px;border:1px solid var(--line);cursor:zoom-in}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--sub);margin-left:8px}
.badge.ok{color:var(--ok);border-color:var(--ok)}
.badge.reroll{color:var(--acc);border-color:var(--acc)}
footer{margin-top:30px;color:var(--sub);font-size:12px;text-align:center}
</style></head><body><div class="wrap">
<header><h1>狸猫<span class="h3">H3</span>工作流 · 创作台</h1></header>
<div class="sub">MiniMax H3 开源模型 · 出图硬闸+文字校验闸自动值守 · 无需进入 ComfyUI</div>
<div class="tabs">
  <div class="tab on" data-t="t2i" onclick="switchTab('t2i')">文生图 · 4K直出</div>
  <div class="tab" data-t="edit" onclick="switchTab('edit')">图生图</div>
</div>

<div id="panel-t2i" class="card">
  <label>提示词</label>
  <textarea id="t2i-prompt" placeholder="描述画面内容，例如：废土黄昏，男孩骑着改装电动车驶过沙丘…"></textarea>
  <label>图内期望文字（选填，触发文字校验闸：不符自动换种子重roll）</label>
  <input type="text" id="t2i-text" placeholder="例如：福福（留空则不校验）">
  <div class="row">
    <div><label>画幅比例</label><select id="t2i-ratio"><option value="16:9" selected>16:9 宽银幕</option><option value="3:2">3:2</option><option value="1:1">1:1 方形</option><option value="4:3">4:3</option><option value="2:3">2:3 竖幅</option><option value="9:16">9:16 竖屏</option></select></div>
    <div><label>分辨率档</label><select id="t2i-mp"><option value="16" selected>16MP · 4K直出</option><option value="8">8MP · 快速</option></select></div>
    <div><label>种子（留空随机）</label><input type="number" id="t2i-seed" placeholder="随机"></div>
  </div>
  <button class="go" id="t2i-go" onclick="submit('t2i')">生成</button>
</div>

<div id="panel-edit" class="card" style="display:none">
  <label>参考图（第1张=待编辑图，可追加参考图，最多16张）</label>
  <input type="file" id="edit-file" accept="image/*" multiple onchange="showThumb(this)">
  <div id="edit-thumbs" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px"></div>
  <label>编辑指令</label>
  <textarea id="edit-prompt" placeholder="Replace the sky with a warm dusk..."></textarea>
  <label>图内期望文字（选填）</label>
  <input type="text" id="edit-text">
  <div class="row">
    <div><label>画幅比例</label><select id="edit-ratio"><option value="auto" selected>跟随参考图</option><option value="16:9">16:9 宽银幕</option><option value="3:2">3:2</option><option value="1:1">1:1 方形</option><option value="4:3">4:3</option><option value="2:3">2:3 竖幅</option><option value="9:16">9:16 竖屏</option></select></div>
    <div><label>分辨率档</label><select id="edit-mp"><option value="16" selected>16MP · 4K直出</option><option value="8">8MP · 快速</option></select></div>
    <div><label>种子（留空随机）</label><input type="number" id="edit-seed" placeholder="随机"></div>
  </div>
  <button class="go" id="edit-go" onclick="submit('edit')">生成</button>
</div>

<div id="state"></div>
<div id="log"></div>
<div id="imgs"></div>
<footer>狸猫AI · limao-h3-suite 自研质检节点全链值守 · 出图即交付</footer>
</div>
<script>
let curTab='t2i', pollTimer=null;
function switchTab(t){curTab=t;document.querySelectorAll('.tab').forEach(e=>e.classList.toggle('on',e.dataset.t===t));
 document.getElementById('panel-t2i').style.display=t==='t2i'?'block':'none';
 document.getElementById('panel-edit').style.display=t==='edit'?'block':'none';}
async function submit(mode){
 const fd=new FormData();fd.append('mode',mode);
 const p=document.getElementById(mode+'-prompt').value.trim();
 if(!p){alert('提示词不能为空');return}
 fd.append('prompt',p);
 fd.append('text',document.getElementById(mode+'-text').value.trim());
 const s=document.getElementById(mode+'-seed').value; if(s) fd.append('seed',s);
 fd.append('mp',document.getElementById(mode+'-mp').value);
 if(mode==='t2i') fd.append('ratio',document.getElementById('t2i-ratio').value);
 if(mode==='edit'){
  fd.append('ratio',document.getElementById('edit-ratio').value);
  const fs=document.getElementById('edit-file').files;
  if(!fs.length){alert('请先上传参考图（第1张=待编辑图）');return}
  if(fs.length>16){alert('参考图最多16张');return}
  for(const f of fs) fd.append('file',f)}
 const go=document.getElementById(mode+'-go');go.disabled=true;go.textContent='提交中…';
 try{
  const r=await fetch('/api/task',{method:'POST',body:fd});const j=await r.json();
  if(!j.ok){alert(j.err||'提交失败');go.disabled=false;go.textContent='生成';return}
  watch(j.id,go);
 }catch(e){alert('网络错误: '+e);go.disabled=false;go.textContent='生成'}
}
function showThumb(inp){
 const box=document.getElementById('edit-thumbs');
 box.innerHTML='';
 const fs=Array.from(inp.files||[]).slice(0,16);
 fs.forEach((f,idx)=>{
  const wrap=document.createElement('div');
  wrap.style.cssText='position:relative;width:110px';
  const im=document.createElement('img');
  im.src=URL.createObjectURL(f);
  im.style.cssText='width:110px;height:82px;object-fit:cover;border-radius:8px;border:1px solid var(--line);cursor:zoom-in';
  im.onclick=()=>window.open(im.src);
  const tag=document.createElement('div');
  tag.textContent=idx===0?'待编辑':('参考'+idx);
  tag.style.cssText='position:absolute;left:4px;top:4px;background:rgba(0,0,0,.65);color:'+(idx===0?'#ff8a3d':'#9aa3b2')+';font-size:11px;padding:1px 7px;border-radius:6px';
  wrap.appendChild(im);wrap.appendChild(tag);box.appendChild(wrap);
 });
 if(fs.length>16) alert('参考图最多16张，已只取前16张');
}
function watch(id,go){
 const st=document.getElementById('state'),lg=document.getElementById('log'),im=document.getElementById('imgs');
 st.style.display='block';st.className='run';st.textContent='任务已提交，正在排队/采样…（4K档约2-4分钟）';lg.style.display='block';im.innerHTML='';
 clearInterval(pollTimer);
 pollTimer=setInterval(async()=>{
  const j=await (await fetch('/api/task/'+id)).json();
  lg.textContent=(j.log||'').split('\\n').slice(-14).join('\\n');lg.scrollTop=lg.scrollHeight;
  if(j.state==='running'&&st.className!=='run'){st.className='run'}
  if(j.state==='done'){
   clearInterval(pollTimer);go.disabled=false;go.textContent='生成';
   st.className='ok';st.innerHTML='完成 · 用时 '+Math.round(j.secs)+'s '+(j.reroll>0?('<span class="badge reroll">文字闸重roll '+j.reroll+'次</span>'):'')+' <span class="badge ok">全部防线通过</span>';
   im.innerHTML=j.images.map(f=>'<img src="/image/'+encodeURIComponent(f)+'" onclick="window.open(this.src)">').join('');
  }
  if(j.state==='error'){clearInterval(pollTimer);go.disabled=false;go.textContent='生成';st.className='err';st.textContent='失败：'+(j.err||'见日志');}
 },2500);
}
</script></body></html>"""

def _log_tail(path, n=40):
    try:
        with open(path, errors="ignore") as f:
            return "".join(f.readlines()[-n:])
    except Exception:
        return ""

def _scan_output(since, prefix_ok=("limao", "ComfyUI")):
    out = []
    for root, _, files in os.walk(OUTPUT_DIR):
        for f in files:
            if not f.lower().endswith((".png", ".jpg", ".webp")):
                continue
            p = os.path.join(root, f)
            try:
                if os.path.getmtime(p) >= since - 2:
                    out.append(os.path.relpath(p, OUTPUT_DIR))
            except OSError:
                pass
    return sorted(out, key=lambda p: -os.path.getmtime(os.path.join(OUTPUT_DIR, p)))[:6]

def _run_task(tid, mode, prompt, text, seed, mp, ratio, img_names):
    t = TASKS[tid]
    log = f"/tmp/limaoui_{tid}.log"
    t["log_path"] = log
    since = time.time()
    cmd = [PY, f"/root/run_{mode}.py", "--prompt", prompt]
    if mode == "t2i":
        cmd += ["--ratio", ratio or "16:9"]
        if mp == "8": cmd.append("--8mp")
    if mode == "edit":
        cmd += ["--wf", f"/root/ComfyUI/user/default/workflows/狸猫·H3生图/{os.path.basename(EDIT_WF)}",
                "--imgs"] + list(img_names)
        if mp == "8": cmd.append("--8mp")
        if ratio and ratio != "auto":
            cmd += ["--ratio", ratio]
    if text:
        cmd += ["--text", text, "--max-text-reroll", "3"]
    if seed:
        cmd += ["--seed", str(seed)]
    t["cmd"] = " ".join(cmd)
    with open(log, "w") as f:
        try:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=1500)
        except subprocess.TimeoutExpired:
            t["state"] = "error"; t["err"] = "生成超时（25分钟），已终止"
            return
    t["secs"] = time.time() - since
    out = f.read() if False else _log_tail(log, 60)
    t["log"] = out
    t["images"] = _scan_output(since)
    # 狸猫隐码：产出即注入不可见身份码（图片=元数据+LSB双层，视频=mp4容器元数据）
    for f in t["images"]:
        fp = os.path.join(OUTPUT_DIR, f)
        subprocess.run([PY, "/root/limao-tools/limao_stamp.py", "--file", fp,
                        "--wf", "狸猫H3生图", "--task", tid,
                        "--seed", str(seed or "")], timeout=90)
    rerolls = len(re.findall(r"重roll|重Roll|FAIL|打回", out))
    t["reroll"] = rerolls
    if r.returncode == 0 and t["images"]:
        t["state"] = "done"
    else:
        t["state"] = "error"
        t["err"] = "生成失败，见日志"

@app.route("/")
def index():
    return HTML

@app.route("/image/<path:p>")
def image(p):
    return send_from_directory(OUTPUT_DIR, p)

@app.route("/api/task", methods=["POST"])
def create():
    mode = request.form.get("mode", "t2i")
    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify(ok=False, err="提示词为空")
    if not GPU_LOCK.acquire(blocking=False):
        return jsonify(ok=False, err="有任务正在生成中，请稍候（单卡队列）")
    GPU_LOCK.release()
    tid = uuid.uuid4().hex[:12]
    img_name = None
    if mode == "edit":
        fs = request.files.getlist("file")
        if not fs:
            return jsonify(ok=False, err="编辑模式需要上传参考图（第1张=待编辑图）")
        img_names = []
        for idx, f in enumerate(fs[:16], start=1):
            ext = os.path.splitext(f.filename)[1].lower() or ".png"
            img_name = f"limaoui_{tid}_{idx}{ext}"
            f.save(os.path.join(INPUT_DIR, img_name))
            img_names.append(img_name)
        # 画幅比例不裁切参考图 —— 由 run_edit.py 覆盖条件化节点 width/height 实现
    else:
        img_names = None
    TASKS[tid] = {"state": "running", "t0": time.time(), "images": [], "log": "", "reroll": 0}
    th = threading.Thread(target=_run_task, args=(tid, mode, prompt,
        request.form.get("text", "").strip(), request.form.get("seed", "").strip(),
        request.form.get("mp", "16"), request.form.get("ratio", "auto"), img_names), daemon=True)
    th.start()
    return jsonify(ok=True, id=tid)

@app.route("/api/task/<tid>")
def status(tid):
    t = TASKS.get(tid)
    if not t:
        return jsonify(state="error", err="任务不存在")
    if t["state"] == "running" and t.get("log_path"):
        t["log"] = _log_tail(t["log_path"], 30)
        t["secs"] = time.time() - t["t0"]
    return jsonify(state=t["state"], log=t.get("log", ""), images=t.get("images", []),
                   secs=t.get("secs", 0), reroll=t.get("reroll", 0), err=t.get("err", ""))

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=6008, threaded=True)
