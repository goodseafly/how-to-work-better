# -*- coding: utf-8 -*-
"""
【已停用，保留备查】生成《高性价比职场指南》单文件 HTML 全本阅读器。

这个脚本已被 tools/build-offline.py 取代（后者基于官方查看器外壳，功能一样并多出
长文与核实记录两层）。保留下来只为回溯早期实现。产物文件名已改成
「高性价比职场指南-旧版阅读器.html」，不会再覆盖 build-offline.py 的正式产物。
里面的期望值还是 505 条时代的，跑起来会告警，属正常。

- 只读 book/*.md，绝不修改原始文件。
- 输出：BOOK_OUT 目录（默认在书的上一级）里的「高性价比职场指南-旧版阅读器.html」
- 只用标准库；可重复运行、幂等。

运行：
  python tools/legacy-build-viewer.py
"""

import os
import re
import glob
import html
import datetime
from collections import Counter, OrderedDict

# ----------------------------------------------------------------------------
# 路径常量
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK_DIR = os.path.join(BASE_DIR, "book")
OUT_HTML = os.path.join(os.environ.get("BOOK_OUT") or os.path.dirname(BASE_DIR),
                        "高性价比职场指南-旧版阅读器.html")

# 期望值（用于自检告警，不参与渲染）
EXPECT_TOTAL = 505
EXPECT_LEVELS = {"A": 458, "B": 39, "C": 8}

# 五个筛选维度：展示名 -> 取值顺序
DIMENSIONS = OrderedDict([
    ("钱", ["0", "少", "多"]),
    ("时间", ["少", "中", "多"]),
    ("毅力", ["否", "些", "是"]),
    ("收益", ["大", "中", "小"]),
    ("口径", ["金钱", "时间", "健康", "岗位", "自由"]),
])
DIM_KEY = {"钱": "money", "时间": "time", "毅力": "grit", "收益": "gain", "口径": "scope"}

FIELD_ORDER = ["成本", "说人话", "收益", "证据等级", "来源", "备注"]
EXTRA_FIELDS = {"证据等级", "来源", "备注"}  # 紧凑模式下折叠

# ----------------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------------
RE_SEC = re.compile(r"^#\s+(\d+)\.\s+(.*)$")
RE_ITEM = re.compile(r"^###\s+(\d+)\.\s+(.*)$")
RE_FIELD = re.compile(r"^-\s*(\S+?)：\s*(.*)$")
RE_LABEL = re.compile(r"成本标签:\s*(.+?)\s*-->")


def parse_section(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    num = name = None
    intro_lines = []
    items = []
    cur = None
    cur_field = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[←"):
            continue

        m = RE_SEC.match(line)
        if m:
            num, name = int(m.group(1)), m.group(2).strip()
            continue

        m = RE_ITEM.match(line)
        if m:
            if cur is not None:
                items.append(cur)
            cur = {
                "num": int(m.group(1)),
                "title": m.group(2).strip(),
                "fields": OrderedDict(),
                "label": {},
            }
            cur_field = None
            continue

        if line.startswith("<!--"):
            mm = RE_LABEL.search(line)
            if mm and cur is not None:
                for kv in mm.group(1).split():
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        cur["label"][k] = v
            continue

        m = RE_FIELD.match(line)
        if m and cur is not None:
            cur_field = m.group(1)
            cur["fields"][cur_field] = m.group(2)
            continue

        # 续行：接到上一个字段；条目开始前的行算本节导览
        if cur is not None and cur_field:
            cur["fields"][cur_field] += line
        elif cur is None:
            intro_lines.append(line)

    if cur is not None:
        items.append(cur)

    return {
        "num": num,
        "name": name,
        "intro": "".join(intro_lines).strip(),
        "items": items,
    }


def load_book():
    files = sorted(glob.glob(os.path.join(BOOK_DIR, "*.md")))
    sections = [parse_section(p) for p in files]
    sections = [s for s in sections if s["num"] is not None]
    sections.sort(key=lambda s: s["num"])
    return sections


# ----------------------------------------------------------------------------
# 行内 Markdown -> HTML
# ----------------------------------------------------------------------------
RE_URL_ANGLE = re.compile(r"<((?:https?://)[^<>\s]+)>")
RE_URL_BARE = re.compile(r"(https?://[^\s<>\"]+)")
RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_TRAIL = "。，；、）】》.,;："


def _make_link(url):
    core = url.rstrip(_TRAIL)
    tail = url[len(core):]
    href = html.escape(core, quote=True)
    a = '<a href="%s" target="_blank" rel="noopener">%s</a>' % (href, html.escape(core))
    if tail:
        a += html.escape(tail)
    return a


def md_inline(text):
    """URL 转链接、**加粗** 转 <strong>，其余按纯文本转义。"""
    if not text:
        return ""
    store = []

    def keep(s):
        store.append(s)
        return "\x00%d\x00" % (len(store) - 1)

    text = RE_URL_ANGLE.sub(lambda m: keep(_make_link(m.group(1))), text)
    text = RE_URL_BARE.sub(lambda m: keep(_make_link(m.group(1))), text)

    out = html.escape(text)
    out = RE_BOLD.sub(r"<strong>\1</strong>", out)
    out = re.sub(r"\x00(\d+)\x00", lambda m: store[int(m.group(1))], out)
    return out


def esc_attr(s):
    return html.escape(str(s), quote=True)


def write_text(path, text):
    """写文件，LF 换行。个别环境下已存在的文件被写保护，退一步先删再写。"""
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except PermissionError:
        if os.path.exists(path):
            os.remove(path)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


# ----------------------------------------------------------------------------
# HTML 片段
# ----------------------------------------------------------------------------
def render_item(sec_num, it):
    iid = "s%d-%d" % (sec_num, it["num"])
    label = it["label"]
    money = label.get("钱", "")
    timev = label.get("时间", "")
    grit = label.get("毅力", "")
    gain = label.get("收益", "")
    scope = label.get("口径", "")

    ev = it["fields"].get("证据等级", "").strip()
    ev_cls = {"A": "ev-a", "B": "ev-b", "C": "ev-c"}.get(ev, "ev-c")

    chips = []
    for k, v in (("钱", money), ("时间", timev), ("毅力", grit), ("收益", gain), ("口径", scope)):
        if v:
            chips.append('<span class="chip">%s%s</span>' % (esc_attr(k), esc_attr(v)))

    rows = []
    for field in FIELD_ORDER:
        raw = it["fields"].get(field, "")
        if raw == "" and field not in it["fields"]:
            continue
        cls = "row"
        if field == "说人话":
            cls += " say"
        if field in EXTRA_FIELDS:
            cls += " extra"
        rows.append(
            '<div class="%s"><span class="k">%s</span><div class="v" data-k="%s">%s</div></div>'
            % (cls, esc_attr(field), esc_attr(field), md_inline(raw))
        )

    return (
        '<article class="item" id="%s" data-sec="%d" data-money="%s" data-time="%s"'
        ' data-grit="%s" data-gain="%s" data-scope="%s">\n'
        '  <div class="item-head">\n'
        '    <span class="seq">%d-%d</span>\n'
        '    <h4 class="item-title">%d. %s</h4>\n'
        '    <span class="ev %s">%s</span>\n'
        '    <a class="anchor" href="#%s" title="链接到这一条">&#182;</a>\n'
        '  </div>\n'
        '  <div class="chips">%s</div>\n'
        '  <div class="fields">%s</div>\n'
        '</article>'
    ) % (
        iid, sec_num, esc_attr(money), esc_attr(timev), esc_attr(grit),
        esc_attr(gain), esc_attr(scope),
        sec_num, it["num"],
        it["num"], md_inline(it["title"]),
        ev_cls, esc_attr(ev),
        iid,
        "".join(chips),
        "".join(rows),
    )


def render_section(sec):
    num = sec["num"]
    items_html = "\n".join(render_item(num, it) for it in sec["items"])
    lede = ""
    if sec["intro"]:
        lede = '<p class="lede">%s</p>' % md_inline(sec["intro"])
    return (
        '<section class="sec" id="sec%d" data-sec="%d">\n'
        '  <div class="sec-head">\n'
        '    <h2><span class="snum">%d</span><span class="sec-title-cn">%s</span></h2>\n'
        '    <button class="only-btn" data-sec="%d" type="button">只看这一节</button>\n'
        '  </div>\n'
        '  %s\n'
        '  <div class="items">\n%s\n  </div>\n'
        '</section>'
    ) % (num, num, num, md_inline(sec["name"]), num, lede, items_html)


def render_toc(sections):
    out = []
    for sec in sections:
        out.append(
            '<a href="#sec%d" data-sec="%d"><span class="tn">%d.</span>'
            '<span class="tt">%s</span><span class="tb">%d</span></a>'
            % (sec["num"], sec["num"], sec["num"], md_inline(sec["name"]), len(sec["items"]))
        )
    return "\n".join(out)


def render_pills(counters):
    groups = []
    for dim, values in DIMENSIONS.items():
        key = DIM_KEY[dim]
        pills = []
        for v in values:
            c = counters[dim].get(v, 0)
            pills.append(
                '<button class="pill" type="button" data-dim="%s" data-val="%s">%s=%s <span class="c">(%d)</span></button>'
                % (key, esc_attr(v), esc_attr(dim), esc_attr(v), c)
            )
        groups.append('<div class="fgroup">%s</div>' % "".join(pills))
    return "\n".join(groups)


# ----------------------------------------------------------------------------
# 静态资源
# ----------------------------------------------------------------------------
CSS = r"""
  :root{
    --ink:#1c1b19; --ink-2:#4a4741; --ink-3:#7a756c;
    --line:#e2ded6; --line-2:#efece6; --bg:#faf8f5; --card:#ffffff;
    --blue:#3451b2; --green:#18794e; --brown:#915930; --red:#b0332f; --amber:#a87a12;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    font-size:15.5px;line-height:1.78;-webkit-font-smoothing:antialiased;}

  .layout{display:flex;align-items:flex-start;max-width:1360px;margin:0 auto;}

  /* 左侧目录 */
  .side{position:sticky;top:0;flex:0 0 280px;width:280px;height:100vh;overflow:auto;
    border-right:1px solid var(--line);padding:22px 16px 44px;background:var(--bg);}
  .side-head{display:flex;align-items:center;justify-content:space-between;gap:8px;
    font-size:12px;letter-spacing:.1em;color:var(--ink-3);text-transform:uppercase;margin-bottom:12px;}
  .side-close{display:none;background:none;border:none;font:inherit;color:var(--ink-3);cursor:pointer;letter-spacing:0;text-transform:none;font-size:12.5px;}
  #toTop{font-family:inherit;font-size:12px;color:var(--ink-3);background:var(--card);
    border:1px solid var(--line);border-radius:999px;padding:3px 11px;cursor:pointer;letter-spacing:0;text-transform:none;}
  #toTop:hover{border-color:var(--blue);color:var(--blue);}
  .toc{display:flex;flex-direction:column;gap:2px;}
  .toc a{display:flex;align-items:baseline;gap:8px;text-decoration:none;color:var(--ink-2);
    font-size:13.5px;padding:5px 8px;border-radius:6px;line-height:1.45;}
  .toc a:hover{background:#f2f0ea;color:var(--ink);}
  .toc a .tn{color:var(--ink-3);font-size:12px;flex:0 0 auto;min-width:1.5em;text-align:right;font-variant-numeric:tabular-nums;}
  .toc a .tt{flex:1 1 auto;}
  .toc a .tb{font-size:11px;color:var(--ink-3);background:#f4f1ec;border-radius:999px;padding:0 7px;flex:0 0 auto;font-variant-numeric:tabular-nums;}

  .toc-toggle{display:none;}
  #backdrop{display:none;}

  /* 右栏 */
  .main{flex:1 1 auto;min-width:0;padding:0 34px 90px;}
  .col{max-width:900px;}

  .hero{padding:42px 0 26px;border-bottom:2px solid var(--ink);}
  .kicker{font-size:12.5px;letter-spacing:.16em;color:var(--ink-3);text-transform:uppercase;margin-bottom:16px;}
  .hero h1{font-family:Georgia,"Songti SC","SimSun",serif;font-size:36px;line-height:1.25;margin:0;font-weight:700;}
  .hero h1 small{display:block;font-size:18px;font-weight:400;color:var(--ink-2);margin-top:10px;line-height:1.65;font-family:inherit;}
  .hero-note{color:var(--ink-2);margin:14px 0 0;font-size:14.5px;}
  .facts{display:flex;flex-wrap:wrap;margin-top:24px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--card);}
  .fact{flex:1 1 120px;padding:13px 16px;border-right:1px solid var(--line-2);}
  .fact:last-child{border-right:none;}
  .fact b{display:block;font-size:20px;line-height:1.2;font-variant-numeric:tabular-nums;}
  .fact span{font-size:12px;color:var(--ink-3);display:block;margin-top:4px;}

  /* 工具栏 */
  .toolbar{position:sticky;top:0;z-index:30;background:var(--bg);
    border-bottom:1px solid var(--line);padding:12px 0 10px;margin-bottom:10px;}
  .tb-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
  .search{flex:1 1 260px;display:flex;align-items:center;gap:8px;border:1px solid var(--line);
    background:var(--card);border-radius:8px;padding:7px 12px;}
  .search input{border:none;outline:none;background:transparent;font:inherit;font-size:14px;color:var(--ink);width:100%;}
  .count{font-size:12.5px;color:var(--ink-3);white-space:nowrap;font-variant-numeric:tabular-nums;}
  .btn{font-family:inherit;font-size:12.5px;color:var(--ink-2);background:var(--card);
    border:1px solid var(--line);border-radius:999px;padding:6px 13px;cursor:pointer;}
  .btn:hover{border-color:var(--blue);color:var(--blue);}
  .switch{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--ink-2);cursor:pointer;user-select:none;}
  .switch input{accent-color:var(--blue);width:15px;height:15px;cursor:pointer;}
  .fgroup{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;}
  .pill{font-family:inherit;font-size:12px;color:var(--ink-2);background:var(--card);
    border:1px solid var(--line);border-radius:999px;padding:3px 10px;cursor:pointer;line-height:1.7;white-space:nowrap;}
  .pill .c{color:var(--ink-3);font-variant-numeric:tabular-nums;}
  .pill:hover{border-color:var(--blue);}
  .pill.on{background:var(--blue);border-color:var(--blue);color:#fff;}
  .pill.on .c{color:rgba(255,255,255,.78);}
  .mode-bar{display:none;align-items:center;gap:10px;margin-top:8px;font-size:12.5px;color:var(--ink-2);}
  .mode-bar.show{display:flex;}
  .mode-bar b{color:var(--ink);}

  /* 节 */
  .sec{margin-top:48px;scroll-margin-top:150px;}
  .sec.flash .sec-head{border-bottom-color:var(--blue);}
  .sec-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
    border-bottom:2px solid var(--ink);padding-bottom:10px;transition:border-color .3s;}
  .sec-head h2{margin:0;font-family:Georgia,"Songti SC","SimSun",serif;font-size:23px;font-weight:700;flex:1 1 auto;line-height:1.4;}
  .sec-head .snum{font-size:13px;color:var(--ink-3);font-weight:500;margin-right:8px;letter-spacing:.08em;font-family:inherit;}
  .only-btn{font-family:inherit;font-size:12px;color:var(--ink-3);background:transparent;
    border:1px solid var(--line);border-radius:999px;padding:3px 11px;cursor:pointer;white-space:nowrap;}
  .only-btn:hover{border-color:var(--blue);color:var(--blue);}
  .lede{color:var(--ink-2);margin:14px 0 6px;max-width:80ch;font-size:14.6px;}

  /* 条目卡片 */
  .item{background:var(--card);border:1px solid var(--line);border-radius:10px;
    padding:16px 20px;margin:0 0 14px;scroll-margin-top:170px;transition:box-shadow .3s,border-color .3s;}
  .item.flash{border-color:var(--blue);box-shadow:0 0 0 3px rgba(52,81,178,.14);}
  .item.hide,.sec.hide{display:none;}
  .item-head{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;}
  .seq{font-family:Consolas,Menlo,monospace;font-size:11.5px;color:var(--blue);
    background:#eef1fb;border-radius:999px;padding:1px 9px;font-weight:700;flex:0 0 auto;}
  .item-title{margin:0;font-size:16px;font-weight:700;line-height:1.5;flex:1 1 auto;min-width:0;}
  .ev{display:inline-block;font-size:11px;font-weight:700;padding:0 7px;border-radius:4px;line-height:1.85;flex:0 0 auto;}
  .ev-a{background:#e4f2ea;color:var(--green);}
  .ev-b{background:#e8ecf9;color:var(--blue);}
  .ev-c{background:#f0ede7;color:var(--ink-3);}
  .anchor{color:var(--ink-3);text-decoration:none;font-size:15px;opacity:.45;flex:0 0 auto;line-height:1;}
  .anchor:hover{opacity:1;color:var(--blue);}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0 0;}
  .chip{font-size:11.5px;color:var(--ink-3);background:#f4f1ec;border:1px solid var(--line-2);
    border-radius:999px;padding:1px 9px;line-height:1.7;}
  .fields{margin:12px 0 0;}
  .row{display:grid;grid-template-columns:76px 1fr;gap:10px;padding:7px 0;border-top:1px solid var(--line-2);font-size:14.2px;}
  .row .k{color:var(--ink-3);font-weight:600;font-size:12.8px;padding-top:1px;}
  .row .v{color:var(--ink-2);min-width:0;overflow-wrap:anywhere;word-break:break-all;}
  .row .v a{color:var(--blue);text-decoration:none;border-bottom:1px solid #cdd6f0;}
  .row .v a:hover{border-bottom-color:var(--blue);}
  .row .v strong{color:var(--ink);}
  .row.say{background:#f6f4ef;border-radius:8px;padding:10px 12px;}
  .row.say .k{color:var(--ink-2);}
  .row.say .v{color:var(--ink);border-left:3px solid var(--blue);padding-left:12px;font-size:14.6px;}
  body.compact .row.extra{display:none;}

  .foot{margin-top:70px;padding-top:22px;border-top:1px solid var(--line);
    font-size:12.5px;color:var(--ink-3);line-height:1.9;}

  @media(max-width:900px){
    .layout{display:block;}
    .toc-toggle{display:block;position:sticky;top:0;z-index:40;width:100%;text-align:left;
      font-family:inherit;font-size:13.5px;color:var(--ink);background:var(--bg);border:none;
      border-bottom:1px solid var(--line);padding:11px 2px;cursor:pointer;}
    .side{position:fixed;top:0;left:0;width:min(86vw,340px);height:100%;z-index:60;
      padding:18px 16px 44px;transform:translateX(-103%);transition:transform .2s ease;
      box-shadow:0 10px 40px rgba(0,0,0,.16);}
    .side.open{transform:translateX(0);}
    .side-close{display:block;}
    #backdrop{position:fixed;inset:0;background:rgba(28,27,25,.34);z-index:55;}
    #backdrop.show{display:block;}
    .main{padding:0 18px 70px;}
    .toolbar{position:static;}
    .hero h1{font-size:28px;}
    .sec{scroll-margin-top:20px;}
    .item{scroll-margin-top:20px;}
    .row{grid-template-columns:64px 1fr;}
  }
"""

JS = r"""
(function(){
  var items = Array.prototype.slice.call(document.querySelectorAll('.item'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('.sec'));
  var qEl = document.getElementById('q');
  var countEl = document.getElementById('count');
  var modeBar = document.getElementById('modeBar');
  var modeName = document.getElementById('modeName');
  var dims = ['money','time','grit','gain','scope'];
  var sets = {};
  dims.forEach(function(d){ sets[d] = {}; });
  var state = { sec: null };

  // 预计算检索文本：标题 + 成本 / 说人话 / 收益 / 备注
  items.forEach(function(el){
    var parts = [];
    var t = el.querySelector('.item-title');
    if (t) parts.push(t.textContent);
    ['成本','说人话','收益','备注'].forEach(function(k){
      var v = el.querySelector('[data-k="' + k + '"]');
      if (v) parts.push(v.textContent);
    });
    el._search = parts.join(' ').toLowerCase();
  });

  function dimActive(d){ return Object.keys(sets[d]).length > 0; }

  function apply(){
    var q = (qEl.value || '').trim().toLowerCase();
    var shown = 0;
    items.forEach(function(el){
      var ok = true;
      if (q && el._search.indexOf(q) < 0) ok = false;
      if (ok) {
        for (var i = 0; i < dims.length; i++) {
          var d = dims[i];
          if (dimActive(d) && !sets[d][el.dataset[d]]) { ok = false; break; }
        }
      }
      if (ok && state.sec !== null && el.dataset.sec !== state.sec) ok = false;
      el.classList.toggle('hide', !ok);
      if (ok) shown++;
    });
    sections.forEach(function(s){
      var vis = s.querySelectorAll('.item:not(.hide)').length;
      s.classList.toggle('hide', vis === 0);
    });
    countEl.textContent = '找到 ' + shown + ' 条';
  }

  // 筛选胶囊
  Array.prototype.forEach.call(document.querySelectorAll('.pill'), function(p){
    p.addEventListener('click', function(){
      var d = p.dataset.dim, v = p.dataset.val;
      if (sets[d][v]) { delete sets[d][v]; p.classList.remove('on'); }
      else { sets[d][v] = true; p.classList.add('on'); }
      apply();
    });
  });

  // 搜索
  qEl.addEventListener('input', apply);

  // 清空筛选
  document.getElementById('clear').addEventListener('click', function(){
    dims.forEach(function(d){ sets[d] = {}; });
    Array.prototype.forEach.call(document.querySelectorAll('.pill.on'), function(p){ p.classList.remove('on'); });
    qEl.value = '';
    apply();
  });

  // 紧凑模式
  document.getElementById('compact').addEventListener('change', function(e){
    document.body.classList.toggle('compact', e.target.checked);
  });

  // 只看本节 / 看全书
  function setMode(sec){
    state.sec = sec;
    if (sec !== null) {
      var secEl = document.querySelector('.sec[data-sec="' + sec + '"]');
      var cn = secEl ? secEl.querySelector('.sec-title-cn') : null;
      modeName.textContent = (cn ? cn.textContent : sec);
      modeBar.classList.add('show');
    } else {
      modeBar.classList.remove('show');
    }
    apply();
  }
  Array.prototype.forEach.call(document.querySelectorAll('.only-btn'), function(b){
    b.addEventListener('click', function(){
      setMode(b.dataset.sec);
      var secEl = document.querySelector('.sec[data-sec="' + b.dataset.sec + '"]');
      if (secEl) secEl.scrollIntoView({ block: 'start' });
    });
  });
  document.getElementById('showAll').addEventListener('click', function(){
    setMode(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // 高亮
  function flash(el){
    if (!el) return;
    el.classList.add('flash');
    window.setTimeout(function(){ el.classList.remove('flash'); }, 1500);
  }

  // 目录点击：跳转并高亮；移动端顺手收起面板
  Array.prototype.forEach.call(document.querySelectorAll('.toc a'), function(a){
    a.addEventListener('click', function(){
      var secEl = document.querySelector('.sec[data-sec="' + a.dataset.sec + '"]');
      flash(secEl);
      closeSide();
    });
  });

  // 深链
  function goHash(){
    var h = location.hash;
    var m = /^#s(\d+)-(\d+)$/.exec(h);
    if (m) {
      var el = document.getElementById('s' + m[1] + '-' + m[2]);
      if (el) { el.scrollIntoView({ block: 'start' }); flash(el); }
      return;
    }
    m = /^#sec(\d+)$/.exec(h);
    if (m) {
      var secEl = document.getElementById('sec' + m[1]);
      if (secEl) { secEl.scrollIntoView({ block: 'start' }); flash(secEl); }
    }
  }
  window.addEventListener('hashchange', goHash);

  // 移动端目录抽屉
  var side = document.getElementById('side');
  var backdrop = document.getElementById('backdrop');
  function closeSide(){ side.classList.remove('open'); backdrop.classList.remove('show'); }
  document.getElementById('tocToggle').addEventListener('click', function(){
    side.classList.toggle('open');
    backdrop.classList.toggle('show', side.classList.contains('open'));
  });
  backdrop.addEventListener('click', closeSide);
  document.getElementById('sideClose').addEventListener('click', closeSide);

  // 回到顶部
  document.getElementById('toTop').addEventListener('click', function(){
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  apply();
  if (location.hash) window.setTimeout(goHash, 80);
})();
"""


# ----------------------------------------------------------------------------
# 组装
# ----------------------------------------------------------------------------
def build_html(sections):
    total = sum(len(s["items"]) for s in sections)
    level_counter = Counter()
    dim_counters = {d: Counter() for d in DIMENSIONS}
    for s in sections:
        for it in s["items"]:
            level_counter[it["fields"].get("证据等级", "").strip()] += 1
            for d in DIMENSIONS:
                dim_counters[d][it["label"].get(d, "")] += 1

    sec_count = len(sections)
    la = level_counter.get("A", 0)
    lb = level_counter.get("B", 0)
    lc = level_counter.get("C", 0)

    gen_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    toc_html = render_toc(sections)
    secs_html = "\n".join(render_section(s) for s in sections)
    pills_html = render_pills(dim_counters)

    head = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>高性价比职场指南 · 全本阅读</title>\n'
        '<style>%s</style>\n'
        '</head>\n'
        '<body>\n'
    ) % CSS

    layout_open = (
        '<div class="layout">\n'
        '<aside class="side" id="side">\n'
        '  <div class="side-head">\n'
        '    <span>目录</span>\n'
        '    <span><button id="toTop" type="button">回到顶部</button>'
        '<button class="side-close" id="sideClose" type="button">关闭</button></span>\n'
        '  </div>\n'
        '  <nav class="toc">\n%s\n  </nav>\n'
        '</aside>\n'
        '<div id="backdrop"></div>\n'
        '<main class="main">\n'
        '<div class="col">\n'
        '<button class="toc-toggle" id="tocToggle" type="button">目录</button>\n'
    ) % toc_html

    hero = (
        '<header class="hero">\n'
        '  <div class="kicker">HowToLiveBetter 体例 · 职场版</div>\n'
        '  <h1>高性价比职场指南<small>打一份工，换回来什么。</small></h1>\n'
        '  <p class="hero-note">每条建议都写明成本、收益、证据等级和原始来源。</p>\n'
        '  <div class="facts">\n'
        '    <div class="fact"><b>%d</b><span>节</span></div>\n'
        '    <div class="fact"><b>%d</b><span>条建议</span></div>\n'
        '    <div class="fact"><b>%d</b><span>证据等级 A</span></div>\n'
        '    <div class="fact"><b>%d</b><span>证据等级 B</span></div>\n'
        '    <div class="fact"><b>%d</b><span>证据等级 C</span></div>\n'
        '  </div>\n'
        '</header>\n'
    ) % (sec_count, total, la, lb, lc)

    toolbar = (
        '<div class="toolbar">\n'
        '  <div class="tb-row">\n'
        '    <label class="search"><input id="q" type="search" placeholder="搜索标题、说人话、收益、备注、成本" autocomplete="off"></label>\n'
        '    <span class="count" id="count">找到 %d 条</span>\n'
        '    <button class="btn" id="clear" type="button">清空筛选</button>\n'
        '    <label class="switch"><input type="checkbox" id="compact">紧凑模式</label>\n'
        '  </div>\n'
        '  %s\n'
        '  <div class="mode-bar" id="modeBar"><span>只看：<b id="modeName"></b></span>'
        '<button class="btn" id="showAll" type="button">看全书</button></div>\n'
        '</div>\n'
    ) % (total, pills_html)

    footer = (
        '<footer class="foot">\n'
        '  <div>体例继承 HowToLiveBetter（CC BY 4.0），每条都写明成本、收益、证据等级和原始来源。</div>\n'
        '  <div>生成于 %s · 由 book/*.md 自动生成，共 %d 节 %d 条。</div>\n'
        '</footer>\n'
    ) % (gen_time, sec_count, total)

    tail = (
        '</div>\n'
        '</main>\n'
        '</div>\n'
        '<script>%s</script>\n'
        '</body>\n'
        '</html>\n'
    ) % JS

    doc = head + layout_open + hero + toolbar + '<div class="content" id="content">\n' + secs_html + '\n</div>\n' + footer + tail

    stats = {
        "total": total,
        "sections": sec_count,
        "levels": level_counter,
        "dims": dim_counters,
        "gen_time": gen_time,
    }
    return doc, stats


# ----------------------------------------------------------------------------
# 自检与输出
# ----------------------------------------------------------------------------
def main():
    sections = load_book()
    doc, stats = build_html(sections)

    assert "\x00" not in doc, "输出里残留了 NUL 占位符"

    write_text(OUT_HTML, doc)

    size = os.path.getsize(OUT_HTML)
    script_size = os.path.getsize(os.path.abspath(__file__))

    print("=" * 60)
    print("每节统计")
    print("=" * 60)
    for s in sections:
        print("  %2d. %-28s %3d 条" % (s["num"], s["name"], len(s["items"])))
    print("-" * 60)
    print("条目总数：%d" % stats["total"])
    lv = stats["levels"]
    print("证据等级分布：A %d / B %d / C %d" % (lv.get("A", 0), lv.get("B", 0), lv.get("C", 0)))
    for d in DIMENSIONS:
        c = stats["dims"][d]
        print("  %s：" % d + "，".join("%s %d" % (v, c.get(v, 0)) for v in DIMENSIONS[d]))

    warn = []
    if stats["total"] != EXPECT_TOTAL:
        warn.append("条目总数 %d != 期望 %d" % (stats["total"], EXPECT_TOTAL))
    if lv.get("A", 0) != EXPECT_LEVELS["A"] or lv.get("B", 0) != EXPECT_LEVELS["B"] or lv.get("C", 0) != EXPECT_LEVELS["C"]:
        warn.append("等级分布 %s != 期望 %s" % (dict(lv), EXPECT_LEVELS))

    print("=" * 60)
    print("HTML 自检")
    print("=" * 60)
    n_item = doc.count('class="item"')
    n_sec = doc.count('class="sec"')
    n_toclinks = len(re.findall(r'<a href="#sec\d+" data-sec="\d+">', doc))
    checks = [
        ("class=\"item\" 出现次数 == 505", n_item, n_item == EXPECT_TOTAL),
        ("section.sec 数量 == 32", n_sec, n_sec == len(sections)),
        ("目录项 <a href=\"#secN\"> 数量 == 32", n_toclinks, n_toclinks == len(sections)),
        ("含 id=\"s16-3\"", 'id="s16-3"' in doc, 'id="s16-3"' in doc),
        ("含 id=\"s32-15\"", 'id="s32-15"' in doc, 'id="s32-15"' in doc),
    ]
    for name, val, ok in checks:
        print("  [%s] %s → %s" % ("OK" if ok else "!!", name, val))

    print("-" * 60)
    print("脚本字节数：%d" % script_size)
    print("HTML 字节数：%d" % size)
    print("输出：%s" % OUT_HTML)

    if warn:
        print("!! 数据差异警告：")
        for w in warn:
            print("   - " + w)
    else:
        print("数据与期望一致（505 / A 458 / B 39 / C 8）")


if __name__ == "__main__":
    main()
