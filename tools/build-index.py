# -*- coding: utf-8 -*-
"""生成《高性价比职场指南》在线检索页 index.html。

沿用官方 HowToLiveBetter 的 index.html 外壳（在线模式：fetch README.md + book/ + docs/），
只换掉属于「人生指南」的内容：标题、描述、关键词、JSON-LD、导语、noscript、侧栏文案、
页脚、导航按钮、口径胶囊、广告位。统计数字由 book/ 现算，改正文后重跑即可。

与 tools/build-offline.py（离线单文件版）配套：同一个外壳，两处输出。

用法：
  python tools/build-index.py
"""
import datetime
import glob
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
OFFICIAL_INDEX = os.path.join(HERE, "shell-index.html")
OUT = os.path.join(ROOT, "index.html")

BOOK_TITLE = "高性价比职场指南"
OFF_NAME = "高性价比人生指南"
OFF_REPO = "https://github.com/eternity4719/HowToLiveBetter"
OFF_SITE = "https://eternity4719.github.io/HowToLiveBetter/"
OFF_BLOB = OFF_BLOB_RAW = "https://github.com/eternity4719/HowToLiveBetter/blob/main/"
SELF_REPO = "https://github.com/goodseafly/how-to-make-work-pay"

TITLE = "%s · 打一份工，换回来什么" % BOOK_TITLE
DESC = ("教你把工资、加班费和没休完的年假一分不少地要回来，社保断了怎么接、被裁时怎么走、怎么不留尾巴。"
        "%d 条建议覆盖劳动合同、社保公积金、工伤生育、竞业保密、裁员维权、跳槽转行、退休养老，"
        "每条写明花掉什么、换回什么、证据有多硬，来源只引官方文件原文和研究文献。")
KEYWORDS = ("职场,劳动合同,社保,公积金,加班费,年休假,工伤,生育,裁员,竞业限制,劳动仲裁,"
            "维权,养老金,灵活就业,性价比")

DOCS = ["被裁之后三十天.md", "劳动仲裁怎么走.md", "入职前先查什么.md"]


def read(p):
    return open(p, "rb").read().decode("utf-8")


def write(p, text):
    data = text.encode("utf-8")
    for _ in range(8):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
        with open(p, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if open(p, "rb").read() == data:
            return
        time.sleep(0.4)
    sys.exit("写回不稳定：" + p)


def must_sub(text, old, new, n=1, label=""):
    c = text.count(old)
    if c != n:
        sys.exit("替换失败（%s）：期望 %d 处，实际 %d 处 —— %r" % (label or "未命名", n, c, old[:70]))
    return text.replace(old, new)


def book_stats():
    """从 book/ 现算：节数、条数、A/B/C 分布、每节条数。"""
    files = sorted(glob.glob(os.path.join(ROOT, "book", "*.md")))
    total, grades, sec_titles = 0, {"A": 0, "B": 0, "C": 0}, []
    for p in files:
        text = read(p)
        m = re.search(r"^# (\d+)\. (.+?)\s*$", text, re.M)
        sec_titles.append((int(m.group(1)), m.group(2).strip()))
        total += len(re.findall(r"^### \d+\.", text, re.M))
        for g in re.findall(r"^- 证据等级：([ABC])", text, re.M):
            grades[g] = grades.get(g, 0) + 1
    sec_titles.sort()
    return {"sections": len(files), "total": total, "grades": grades, "sec_titles": sec_titles}


def main():
    st = book_stats()
    desc = DESC % st["total"]
    html = read(OFFICIAL_INDEX)

    # ---------- 1. 剥掉统计脚本 ----------
    a, b = html.find("<!-- ga:start"), html.find("<!-- ga:end -->")
    if a < 0 or b < 0:
        sys.exit("找不到 GA 剥离标记")
    html = html[:a] + html[b + len("<!-- ga:end -->"):]
    if re.search(r"googletagmanager|google-analytics", html):
        sys.exit("GA 剥离不干净")

    # ---------- 2. head：标题、描述、关键词、社交卡 ----------
    html = must_sub(html,
        '<title>%s · 用最少的钱、时间和精力换回寿命、金钱和人身自由</title>' % OFF_NAME,
        "<title>%s</title>" % TITLE, 1, "title")
    html = must_sub(html,
        '<meta name="description" content="按性价比排序的人生指南：658 条建议，覆盖长寿防病、意外急救、'
        '省钱理财、防骗与法律红线、失业兜底、创业风险、恋爱婚育、出国与技能。每条写明成本、收益、'
        '证据等级和原始出处，可按钱、时间、毅力三个成本维度检索。">',
        '<meta name="description" content="%s">' % desc, 1, "description")
    html = must_sub(html,
        '<meta name="keywords" content="长寿,健康,循证,总死亡率,省钱,理财,防骗,急救,法律常识,'
        '失业救助,劳动仲裁,创业风险,性价比">',
        '<meta name="keywords" content="%s">' % KEYWORDS, 1, "keywords")
    html = must_sub(html, '<meta name="author" content="%s">' % OFF_NAME,
                    '<meta name="author" content="%s">' % BOOK_TITLE, 1, "author")
    # 社交卡与 canonical：没有线上域名，去掉指向上游站点的 URL，og:image 用本地相对路径
    html, n_ca = re.subn(r'<link rel="canonical"[^>]*>\n', "", html)
    html, n_ogurl = re.subn(r'<meta property="og:url"[^>]*>\n', "", html)
    html, n_tw = re.subn(r'<meta name="twitter:[^>]*>\n', "", html)
    if (n_ca, n_ogurl, n_tw) != (1, 1, 4):
        sys.exit("canonical/og:url/twitter 清理数量不对：%d/%d/%d" % (n_ca, n_ogurl, n_tw))
    html = must_sub(html, '<meta property="og:site_name" content="%s">' % OFF_NAME,
                    '<meta property="og:site_name" content="%s">' % BOOK_TITLE, 1, "og:site_name")
    html = must_sub(html, '<meta property="og:title" content="%s">' % OFF_NAME,
                    '<meta property="og:title" content="%s">' % BOOK_TITLE, 1, "og:title")
    html = must_sub(html,
        '<meta property="og:description" content="按性价比排序的人生指南：658 条建议，覆盖长寿防病、意外急救、'
        '省钱理财、防骗与法律红线、失业兜底、创业风险、恋爱婚育、出国与技能。每条写明成本、收益、'
        '证据等级和原始出处，可按钱、时间、毅力三个成本维度检索。">',
        '<meta property="og:description" content="%s">' % desc, 1, "og:description")
    html = must_sub(html, '<meta property="og:image" content="%sog.png">' % OFF_SITE,
                    '<meta property="og:image" content="og.png">', 1, "og:image")
    # JSON-LD 两行（WebSite / Book）：整行删掉——里面写着上游站点的 @id 和 url，本地页没有对应地址
    html, n_ld = re.subn(r'(?m)^\{"@type":"(?:WebSite|Book)".*$\n?', "", html)
    if n_ld != 2:
        sys.exit("JSON-LD 条数不对：%d" % n_ld)

    # ---------- 3. 书名整体替换 ----------
    html = html.replace(OFF_NAME, BOOK_TITLE)

    # ---------- 4. noscript 整块重写 ----------
    a = html.find("<noscript>")
    b = html.find("</noscript>", a)
    ol = "\n".join("      <li>%d. %s</li>" % t for t in st["sec_titles"])
    noscript = (
        "<noscript>\n  <div style=\"max-width:760px;margin:0 auto;padding:32px 20px;line-height:1.7\">\n"
        "    <h1>%s</h1>\n"
        "    <p>%s</p>\n"
        "    <p>本页的筛选功能需要 JavaScript。正文可直接阅读：<a href=\"README.md\">README.md</a> "
        "里的目录，正文在 <a href=\"book/\">book/</a>。</p>\n    <ol>\n%s\n    </ol>\n  </div>\n</noscript>"
        % (BOOK_TITLE, desc, ol))
    html = html[:a] + noscript + html[b + len("</noscript>"):]

    # ---------- 5. 侧栏：口径胶囊、证据等级小注、正文来源说明 ----------
    html = must_sub(html,
        '      <button class="chip" data-v="死亡率" aria-pressed="false">寿命</button>\n'
        '      <button class="chip" data-v="金钱" aria-pressed="false">钱</button>\n'
        '      <button class="chip" data-v="时间" aria-pressed="false">时间精力</button>\n'
        '      <button class="chip" data-v="自由" aria-pressed="false">人身自由</button>',
        '      <button class="chip" data-v="金钱" aria-pressed="false">钱</button>\n'
        '      <button class="chip" data-v="时间" aria-pressed="false">时间</button>\n'
        '      <button class="chip" data-v="健康" aria-pressed="false">健康</button>\n'
        '      <button class="chip" data-v="岗位" aria-pressed="false">岗位</button>\n'
        '      <button class="chip" data-v="自由" aria-pressed="false">人身自由</button>',
        1, "口径胶囊")
    html = must_sub(html, '<div class="gt">证据等级 <small>荟萃/RCT · 有研究 · 共识</small></div>',
                    '<div class="gt">证据等级 <small>官方文件原文 · 单篇研究 · 作者经验</small></div>',
                    1, "证据等级小注")
    html = must_sub(html,
        '    <p>正文与标签来自仓库 <a href="book/">book/</a> 下的 34 个文件，改正文即改这里。</p>',
        '    <p>正文与标签来自本目录 <a href="book/">book/</a> 下的 %d 个文件，与书稿同源。</p>'
        % st["sections"], 1, "正文来源说明")

    # ---------- 6. 删掉广告位 ----------
    a = html.find('<div class="group ad">')
    b = html.find("</aside>", a)
    if a < 0 or b < 0:
        sys.exit("找不到广告块")
    html = html[:a] + html[b:]
    html = must_sub(html,
        "document.getElementById('tip-open').addEventListener('click'",
        "(document.getElementById('tip-open')||{addEventListener(){}}).addEventListener('click'", 1, "tip-open 保护")
    html = must_sub(html, "document.getElementById('tip-open').focus();",
                    "const __t = document.getElementById('tip-open'); if (__t) __t.focus();", 1, "tip-open focus")

    # ---------- 7. 首屏导语 ----------
    html = must_sub(html,
        '      <p>每一条都回答两个问题：花掉什么，换回什么。</p>\n'
        '      <p>换回的算在谁头上也分档：你自己最高，其次配偶和直系亲属，再次朋友同事，陌生人最低——最低不等于零，只是回报的指望小、要连风险一起看。</p>\n'
        '      <p>不用全做：这是一份按性价比排好的备选单，不是任务清单。挑走一两条就算数，剩下的需要时再回来查——想挑省力的，左边把「花钱」选「不花钱」、「要毅力」选「不用」，剩下的就是。作者自己也没做到其中大部分。正文里带虚线的「第 X 条」可以点开，就地看那条写了什么，不用自己翻过去。</p>',
        '      <p>打一份工，换回来什么。你花出去的是钱、时间和毅力，换回来的是钱、时间、健康、岗位和人身自由。</p>\n'
        '      <p>每一条都回答两个问题：花掉什么，换回什么。</p>\n'
        '      <p>证据分 A / B / C 三级：A 是官方文件原文，B 是单篇同行评议研究和学会共识，C 是作者经验。分级说的是「结论能不能追到出处」，不是效果好坏。全国有统一规定的写明文件和数字，各地有差异的只给查询方法，不拿一个地方的数冒充全国。</p>',
        1, "首屏导语")

    # ---------- 8. 长文与 AI 助手两行 ----------
    doc_links = " · ".join('<a href="docs/%s">%s</a>' % (d, d[:-3]) for d in DOCS)
    html, n_doc = re.subn(r'      <div class="doc-links">长文：.*?</div>\n',
                          '      <div class="doc-links">长文：%s</div>\n' % doc_links, html)
    if n_doc != 1:
        sys.exit("长文行替换数量不对：%d" % n_doc)
    html, n_ai = re.subn(r'      <div class="doc-links">AI 助手：.*?</div>\n',
                         '      <div class="doc-links">AI 助手：<a href="skills/workplace-decision-guide/README.md">'
                         '让 Claude Code 或 Codex 照这本书回答你的问题（skill 装法）</a></div>\n', html)
    if n_ai != 1:
        sys.exit("AI 助手行替换数量不对：%d" % n_ai)
    html = must_sub(html, '      <details class="gloss" id="gloss">',
                    '      <div class="doc-links">每条引用的核对过程：<a href="docs/核实记录/00-目录.md">'
                    '核实记录目录</a>（32 节各一篇，页头右侧按钮也可打开）</div>\n'
                    '      <details class="gloss" id="gloss">', 1, "核实记录入口")

    # ---------- 9. 导航按钮 ----------
    html = must_sub(html, '<a class="title" href="./">', '<a class="title" href="#">', 1, "title 链接")
    html = must_sub(html,
        '<a class="icon-btn" href="README.md" title="查看 README.md" aria-label="README">',
        '<a class="icon-btn" href="docs/核实记录/00-目录.md" title="核实记录（每条引用的原文核对）" aria-label="核实记录">',
        1, "README 图标")
    html = must_sub(html,
        '<a class="icon-btn" href="%s" target="_blank" rel="noopener" title="在 GitHub 上查看源仓库" aria-label="GitHub 仓库">' % OFF_REPO,
        '<a class="icon-btn" href="%s" target="_blank" rel="noopener" title="在 GitHub 上查看本仓库" aria-label="GitHub 仓库">' % SELF_REPO,
        1, "仓库图标")
    html = must_sub(html, '      <div class="doc-links">AI 助手：',
                    '      <div class="doc-links">AI 助手：', 1, "noop")

    # ---------- 10. JS 补丁 ----------
    html = must_sub(html, "const REPO_BLOB = '%s';" % OFF_BLOB_RAW, "const REPO_BLOB = '';", 1, "REPO_BLOB")
    old_docpath = re.search(r"function docPathOf\(href\)\{[\s\S]*?\n\}", html).group(0)
    new_docpath = ("function docPathOf(href){\n"
                   "  if (!href) return null;\n"
                   "  try { href = decodeURIComponent(href); } catch (e) {}\n"
                   "  const m = /(?:^|\\/)(docs\\/[^?#]+\\.md)$/.exec(href);\n"
                   "  return m ? m[1] : null;\n"
                   "}")
    html = must_sub(html, old_docpath, new_docpath, 1, "docPathOf")
    html = must_sub(html, "DM.gh.href = dmHref(path);", "DM.gh.hidden = true;", 1, "DM.gh")
    html = must_sub(html,
        "LENS_LABEL = {'死亡率':'换寿命','金钱':'换钱','时间':'换时间精力','自由':'换人身自由'}",
        "LENS_LABEL = {'金钱':'钱','时间':'时间精力','健康':'健康','岗位':'岗位','自由':'人身自由','死亡率':'换寿命'}",
        1, "LENS_LABEL")
    html = must_sub(html, "同一口径（' + LENS_LABEL[e.lens] + '）内可比",
                    "同一口径（' + (LENS_LABEL[e.lens] || e.lens) + '）内可比", 1, "LENS_LABEL 兜底")

    # ---------- 11. 页脚与页眉注释 ----------
    old_foot = re.search(r'<div class="foot">[\s\S]*?</div>\n  </div>', html).group(0)
    new_foot = ('<div class="foot">由 book/ 与 docs/ 自动生成（%s）。'
                '数字口径以条目内标注为准，互不换算。每条引用的原文核对过程见页头右侧的 '
                '<a href="docs/核实记录/00-目录.md">核实记录</a>。'
                '正文按 '
                '<a href="https://creativecommons.org/licenses/by/4.0/deed.zh-hans">CC BY 4.0</a> '
                '发布，转载改编请署名并附原文链接。</div>\n  </div>') % (
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace(old_foot, new_foot)
    html = must_sub(html, "<!doctype html>",
                    "<!-- %s · 在线检索版 · 由 tools/build-index.py "
                    "从 book/ 与 docs/ 生成，正文改动后重跑即可 -->\n<!doctype html>" % BOOK_TITLE, 1, "页眉注释")

    # ---------- 12. 断言 ----------
    for bad in ("高性价比人生指南", "658", "34 个文件", "HowToLiveBetter.html", "epub-latest"):
        if bad in html:
            sys.exit("残留：%s" % bad)
    assert "docs/核实记录/00-目录.md" in html

    write(OUT, html)
    print("已写出 %s：%.1f KB" % (OUT, len(html.encode("utf-8")) / 1024))
    print("  节 %d / 条 %d（A %d、B %d、C %d）" % (st["sections"], st["total"],
          st["grades"]["A"], st["grades"]["B"], st["grades"]["C"]))


if __name__ == "__main__":
    main()
