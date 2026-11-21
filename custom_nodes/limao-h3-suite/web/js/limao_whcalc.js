/* 狸猫·输出画幅计算器 —— 实时算式预览
 * 在节点底部常驻显示计算结果：算式 → 1024 × 576（0.59MP）
 * 修改 resolution / aspect / multiple 任一参数即时刷新；
 * 算法与后端 nodes.py 的 LimaoH3WHCalc 完全一致（含 Python 银行家舍入）。
 * 所有钩子均带 try/catch 防御，任何异常不影响工作流加载与节点创建。 */
(function () {
  "use strict";
  var app = window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app;
  if (!app || typeof app.registerExtension !== "function") {
    console.warn("[LimaoWHCalc] comfyAPI 不可用，实时算式预览未启用");
    return;
  }

  var MP_TABLE = {
    "480P": 400000, "720P": 600000,
    "1K": 1000000, "2K": 4000000,
    "4K": 9000000, "\u8d854K": 16000000, "16MP": 16000000
  };

  /* Python3 round() 的银行家舍入（.5 时取偶数） */
  function pyRound(x) {
    var f = Math.floor(x), d = x - f;
    if (d > 0.5) return f + 1;
    if (d < 0.5) return f;
    return (f % 2 === 0) ? f : f + 1;
  }

  function parsePixels(text) {
    var t = String(text == null ? "" : text).trim().replace(/\uff0c/g, "").replace(/,/g, "");
    if (!t) throw new Error("empty");
    var up = t.toUpperCase();
    for (var k in MP_TABLE) if (up === k.toUpperCase()) return MP_TABLE[k];
    if (up.slice(-2) === "MP") {
      var v = parseFloat(up.slice(0, -2));
      if (isFinite(v) && v > 0) return Math.round(v * 1e6);
      throw new Error("bad MP");
    }
    if (up.slice(-1) === "K") {
      var kp = up.slice(0, -1);
      if (/^\d+(\.\d+)?$/.test(kp)) {
        var kf = parseFloat(kp);
        return Math.round(kf * kf * 1e6);
      }
      throw new Error("bad K");
    }
    if (/^\d+$/.test(t)) return parseInt(t, 10);
    throw new Error("bad");
  }

  function parseAspect(text) {
    var t = String(text == null ? "" : text).trim().replace(/\uff1a/g, ":");
    if (t.indexOf(":") !== -1) {
      var parts = t.split(":");
      var a = parseFloat(parts[0]), b = parseFloat(parts[1]);
      if (!(a > 0 && b > 0)) throw new Error("bad ratio");
      return a / b;
    }
    var v = parseFloat(t);
    if (!(v > 0)) throw new Error("bad ratio");
    return v;
  }

  function compute(resolution, aspect, multiple) {
    var fallback = false, pixels, ratio;
    try { pixels = parsePixels(resolution); } catch (e) { pixels = 600000; fallback = true; }
    try { ratio = parseAspect(aspect); } catch (e) { ratio = 16 / 9; fallback = true; }
    var m = Math.max(8, parseInt(multiple, 10) || 32);
    var h = Math.max(m, pyRound(Math.sqrt(pixels / ratio) / m) * m);
    var w = Math.max(m, pyRound(h * ratio / m) * m);
    return { w: w, h: h, mp: (w * h) / 1e6, fallback: fallback };
  }

  /* 测试钩子：window.__limaoWHCalcTest.compute(...) 可直接核对算法 */
  try { window.__limaoWHCalcTest = { compute: compute, parsePixels: parsePixels, parseAspect: parseAspect }; } catch (e) {}

  function getWidget(node, name) {
    var list = node.widgets || [];
    for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
    return null;
  }

  function drawPreview(ctx, node) {
    try {
      if (node.flags && node.flags.collapsed) return;
      var res = getWidget(node, "resolution");
      var asp = getWidget(node, "aspect");
      var mul = getWidget(node, "multiple");
      var ups = getWidget(node, "upscale_scale");
      var r = compute(res ? res.value : "720P", asp ? asp.value : "16:9", mul ? mul.value : 32);
      ctx.save();
      ctx.font = "600 12px ui-sans-serif, system-ui, sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      var y = node.size[1] - 13;
      var x0 = 10;
      if (r.fallback) {
        ctx.fillStyle = "#e5b567";
        var warn = "\u26a0 \u6863\u4f4d/\u6bd4\u4f8b\u65e0\u6cd5\u8bc6\u522b\uff0c\u6309 720P\u00b716:9 \u56de\u9000\uff1a";
        ctx.fillText(warn, x0, y);
        x0 += ctx.measureText(warn).width + 6;
      } else {
        ctx.fillStyle = "#7bd07b";
        var tag = "\u7b97\u5f0f \u2192";
        ctx.fillText(tag, x0, y);
        x0 += ctx.measureText(tag).width + 8;
      }
      ctx.fillStyle = "#eef4ff";
      var txt = r.w + " \u00d7 " + r.h + "\uff08" + r.mp.toFixed(2) + "MP\uff09";
      if (ups) {
        var u = Math.min(4, Math.max(1, parseFloat(ups.value) || 1.5));
        txt += " \u2192 \u6210\u7247 " + Math.round(r.w * u) + " \u00d7 " + Math.round(r.h * u);
      }
      ctx.fillText(txt, x0, y);
      ctx.restore();
    } catch (e) { /* 绘制失败不影响节点 */ }
  }

  function bindWidgets(node) {
    ["resolution", "aspect", "multiple", "upscale_scale"].forEach(function (nm) {
      try {
        var w = getWidget(node, nm);
        if (!w || w.__lmCalcBound) return;
        w.__lmCalcBound = true;
        var orig = w.callback;
        w.callback = function () {
          var r = orig ? orig.apply(this, arguments) : undefined;
          setTimeout(function () { try { if (node.setDirtyCanvas) node.setDirtyCanvas(true, true); } catch (e) {} }, 0);
          return r;
        };
        if (nm === "resolution" && w.inputEl) {
          w.inputEl.addEventListener("input", function () {
            try { if (node.setDirtyCanvas) node.setDirtyCanvas(true, true); } catch (e) {}
          });
        }
      } catch (e) { /* 单个组件绑定失败不影响其它 */ }
    });
  }

  app.registerExtension({
    name: "limao.h3.whcalc.preview",
    beforeRegisterNodeDef: function (nodeType, nodeData) {
      if (!nodeData) return;
      if (nodeData.name !== "LimaoH3WHCalc" && nodeData.name !== "LimaoH3VideoParams") return;

      /* 节点底部加 26px 预览条空间（properties 标记防止重复加高） */
      var onAdded = nodeType.prototype.onAdded;
      nodeType.prototype.onAdded = function () {
        try {
          if (!this.properties) this.properties = {};
          if (!this.properties.__lmCalcPad) {
            this.properties.__lmCalcPad = true;
            if (this.size && typeof this.size[1] === "number") this.size[1] += 26;
          }
        } catch (e) { /* 加高失败不影响节点 */ }
        if (onAdded) return onAdded.apply(this, arguments);
      };

      var onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        var r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
        try {
          var node = this;
          node.onDrawForeground = function (ctx) { drawPreview(ctx, node); };
          bindWidgets(node);
        } catch (e) { /* 预览初始化失败不影响节点 */ }
        return r;
      };
    }
  });
  console.log("[LimaoWHCalc] \u5b9e\u65f6\u7b97\u5f0f\u9884\u89c8\u5df2\u52a0\u8f7d");
})();
