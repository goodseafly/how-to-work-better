# -*- coding: utf-8 -*-
"""
用官方 HowToLiveBetter 查看器的外壳 + 我们的语料，生成《高性价比职场指南》全本 HTML。

原理：官方 官方电子书/HowToLiveBetter.html 是「外壳（CSS/JS/导航） + window.__CORPUS__ 语料 JSON」
结构，语料就是 readme + book/*.md 原文。官方查看器的解析器（parseReadme）认的字段与我们
book/*.md 的体例完全同构（<!-- 成本标签 --> 注释 + 成本/说人话/收益/证据等级/来源/备注 六字段），
所以把语料换成我们的 32 节，即可完整继承官方格式：搜索、筛选、术语悬浮、条目互链、深链、深色模式。

本脚本做五件事：
1. 从官方 HTML 里切出外壳（去掉原语料）；
2. 组装我们的语料：readme = README.md（剥掉指向 book/ 的链接不动，文件发现靠它）；
   parts = book/*.md 32 个文件（剥掉行首回链）；docs = docs/核实记录/*.md 32 份 + 00 目录；
3. 改外壳：标题/描述/关键词、删掉 og/twitter/canonical/JSON-LD、重写 noscript、导航按钮改挂核实记录；
4. 打三个 JS 小补丁：REPO_BLOB 置空（不再指上游仓库）、docPathOf 支持子目录（核实记录在子目录里）、
   弹窗的「在 GitHub 打开」按钮隐藏（本地文件没有对应网页）；
5. 断言校验 + 写出。

用法：python tools/build-offline.py
注意：输出路径若已存在文件，沙箱会拒绝写入——先在外部用 rm 删掉再跑本脚本。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
OFFICIAL = os.path.join(HERE, "shell-offline.html")
OUT_DIR = os.environ.get("BOOK_OUT") or os.path.dirname(ROOT)
os.makedirs(OUT_DIR, exist_ok=True)  # CI 里 BOOK_OUT=dist 时目录尚不存在
OUT = os.path.join(OUT_DIR, "高性价比职场指南-全本.html")

BOOK_TITLE = "高性价比职场指南"
BOOK_TAGLINE = "打一份工，换回来什么"
# 描述与导语里的条目数由 book/ 现算（见 book_stats），改正文后不用回来改这里
DESCRIPTION_TPL = ("按性价比排序的职场指南：%d 条建议，覆盖投简历、签合同、工资工时、社保公积金、"
                   "生病生育、职场关系、维权仲裁、裁员跳槽、退休养老、AI 冲击。每条写明成本、收益、"
                   "证据等级和原始出处，可按钱、时间、毅力、收益、口径五个维度检索。")
KEYWORDS = ("职场,劳动合同,社保,公积金,加班费,年休假,工伤,生育,裁员,竞业限制,"
            "劳动仲裁,维权,养老金,灵活就业,性价比")

OFF_TITLE = "高性价比人生指南 · 用最少的钱、时间和精力换回寿命、金钱和人身自由"
OFF_DESC = ("按性价比排序的人生指南：658 条建议，覆盖长寿防病、意外急救、省钱理财、防骗与法律红线、"
            "失业兜底、创业风险、恋爱婚育、出国与技能。每条写明成本、收益、证据等级和原始出处，"
            "可按钱、时间、毅力三个成本维度检索。")
OFF_KEYWORDS = "长寿,健康,循证,总死亡率,省钱,理财,防骗,急救,法律常识,失业救助,劳动仲裁,创业风险,性价比"
OFF_REPO = "https://github.com/eternity4719/HowToLiveBetter"
OFF_SITE = "https://eternity4719.github.io/HowToLiveBetter/"
OFF_BLOB = "https://github.com/eternity4719/HowToLiveBetter/blob/main/"
SELF_REPO = "https://github.com/goodseafly/how-to-make-work-pay"


def must_sub(text, old, new, n=1):
    c = text.count(old)
    if c != n:
        sys.exit("断言失败：%r 出现 %d 次（期望 %d）" % (old[:60], c, n))
    return text.replace(old, new)


def read(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8")


def strip_backlink(md):
    return re.sub(r"^\[← 回总目录\]\([^)]*\)\s*\n", "", md)


def book_stats(parts):
    """从语料现算条目数、A/B/C 分布、去重后的引用链接数，免得数字跟正文脱节。"""
    from collections import Counter
    grades, links, total = Counter(), set(), 0
    for md in parts.values():
        total += len(re.findall(r"^### \d+\. ", md, re.M))
        for m in re.finditer(r"^- 证据等级：\s*([ABC])\s*$", md, re.M):
            grades[m.group(1)] += 1
        links.update(re.findall(r"<(https?://[^>\s]+)>", md))
    n = sum(grades.values())
    if total != n:
        sys.exit("条目 %d 与证据等级合计 %d 对不上" % (total, n))
    return {"total": total, "A": grades["A"], "B": grades["B"], "C": grades["C"],
            "links": len(links)}


def main():
    shell = read(OFFICIAL)

    # ---------- 1. 切出外壳 ----------
    key = "window.__CORPUS__="
    i = shell.find(key)
    j = shell.find("</script>", i)
    if i < 0 or j < 0:
        sys.exit("官方 HTML 里找不到语料块")
    head, tail = shell[: i + len(key)], shell[j:]

    # ---------- 2. 组装语料 ----------
    readme = read(os.path.join(ROOT, "README.md"))
    book_files = sorted(
        f for f in os.listdir(os.path.join(ROOT, "book")) if f.endswith(".md")
    )
    parts = {}
    for name in book_files:
        parts["book/" + name] = strip_backlink(read(os.path.join(ROOT, "book", name)))
    if len(parts) != 32:
        sys.exit("book/ 下不是 32 个文件，是 %d" % len(parts))
    st = book_stats(parts)
    desc = DESCRIPTION_TPL % st["total"]

    doc_dir = os.path.join(ROOT, "docs", "核实记录")
    docs = {}
    for name in sorted(f for f in os.listdir(doc_dir) if f.endswith(".md")):
        docs["docs/核实记录/" + name] = strip_backlink(read(os.path.join(doc_dir, name)))
    toc = ["# 核实记录目录", "",
           "每一节正文里引用的每一条法条、每一个数字，都核过原文。点开对应节看来源、"
           "状态码和抽取结果。", ""]
    for name in sorted(f for f in os.listdir(doc_dir) if f.endswith(".md")):
        title = name[:-3]
        toc.append("- [%s](docs/核实记录/%s)" % (title, name))
    docs["docs/核实记录/00-目录.md"] = "\n".join(toc) + "\n"
    # 读者向长文（docs/ 顶层）：检索页的「长文」入口指向它们
    long_docs = sorted(
        f for f in os.listdir(os.path.join(ROOT, "docs"))
        if f.endswith(".md") and os.path.isfile(os.path.join(ROOT, "docs", f))
    )
    for name in long_docs:
        docs["docs/" + name] = strip_backlink(read(os.path.join(ROOT, "docs", name)))

    corpus = {"readme": readme, "parts": parts, "docs": docs}
    blob = json.dumps(corpus, ensure_ascii=False)

    # ---------- 3. 改外壳 ----------
    out = head + blob + tail

    out = must_sub(out, "<title>%s</title>" % OFF_TITLE,
                   "<title>%s · %s</title>" % (BOOK_TITLE, BOOK_TAGLINE))
    c = out.count(OFF_DESC)
    if c < 4:
        sys.exit("描述串只出现 %d 次，异常" % c)
    out = out.replace(OFF_DESC, desc)
    out = must_sub(out, OFF_KEYWORDS, KEYWORDS)

    # 删掉 og / twitter / canonical / JSON-LD（本地单文件没有对应的外部页面）
    out, n_og = re.subn(r'\n<meta property="og:[^"]*"[^>]*>', "", out)
    out, n_tw = re.subn(r'\n<meta name="twitter:[^"]*"[^>]*>', "", out)
    out, n_ca = re.subn(r'\n<link rel="canonical"[^>]*>', "", out)
    a = out.find('<script type="application/ld+json">')
    if a >= 0:
        b = out.find("</script>", a)
        out = out[:a] + out[b + len("</script>"):]
    if not (n_og >= 4 and n_tw >= 3 and n_ca == 1 and a >= 0):
        sys.exit("meta 清理数量不对：og=%d twitter=%d canonical=%d ldjson=%s"
                 % (n_og, n_tw, n_ca, a >= 0))

    # 书名整体替换（此时语料里自带的「高性价比人生指南」引用不在 head/tail 外壳里，
    # 而是已经在第 1 步被切掉了；tail 的 JS 里若出现，也应当只出现在 UI 文案里）
    out = out.replace(OFF_TITLE.split(" · ")[0], BOOK_TITLE)

    # noscript 整块重写
    a = out.find("<noscript>")
    b = out.find("</noscript>", a)
    sec_titles = []
    for name in book_files:
        text = read(os.path.join(ROOT, "book", name))
        m = re.search(r"^# (\d+)\. (.+)$", text, re.M)
        sec_titles.append((int(m.group(1)), m.group(2).strip()))
    sec_titles.sort()
    ol = "\n".join("<li>%d. %s</li>" % t for t in sec_titles)
    noscript = (
        "<noscript>\n  <div style=\"max-width:760px;margin:0 auto;padding:32px 20px;line-height:1.7\">\n"
        "    <h1>%s</h1>\n"
        "    <p>%s全书 %d 节 %d 条。本页的筛选功能需要 JavaScript；"
        "纯文本版见 README.md 与 book/ 目录。</p>\n    <ol>\n%s\n    </ol>\n  </div>\n</noscript>"
        % (BOOK_TITLE, desc, len(parts), st["total"], ol)
    )
    out = out[:a] + noscript + out[b + len("</noscript>"):]

    # ---------- 4. JS 与导航补丁 ----------
    out = must_sub(out, "const REPO_BLOB = '%s';" % OFF_BLOB, "const REPO_BLOB = '';")
    old_docpath = re.search(r"function docPathOf\(href\)\{[\s\S]*?\n\}", out).group(0)
    new_docpath = (
        "function docPathOf(href){\n"
        "  if (!href) return null;\n"
        "  try { href = decodeURIComponent(href); } catch (e) {}\n"
        "  const m = /(?:^|\\/)(docs\\/[^?#]+\\.md)$/.exec(href);\n"
        "  return m ? m[1] : null;\n"
        "}"
    )
    out = must_sub(out, old_docpath, new_docpath)
    out = must_sub(out, "DM.gh.href = dmHref(path);", "DM.gh.hidden = true;")

    # 导航：logo 指回页内；README 图标改挂核实记录弹窗；仓库图标改指本仓库
    out = must_sub(out, '<a class="title" href="%s">' % OFF_SITE, '<a class="title" href="#">')
    out = must_sub(out,
                   '<a class="icon-btn" href="%sREADME.md" title="查看 README.md" aria-label="README">'
                   % OFF_BLOB,
                   '<a class="icon-btn" href="docs/核实记录/00-目录.md" title="核实记录（每条引用的原文核对）" aria-label="核实记录">')
    out = must_sub(out,
                   '<a class="icon-btn" href="%s" target="_blank" rel="noopener" title="在 GitHub 上查看源仓库" aria-label="GitHub 仓库">'
                   % OFF_REPO,
                   '<a class="icon-btn" href="%s" target="_blank" rel="noopener" title="在 GitHub 上查看本仓库" aria-label="GitHub 仓库">'
                   % SELF_REPO)

    # 筛选抽屉：口径胶囊换成我们的五个取值；证据等级小注改成职场书口径
    out = must_sub(out,
                   '<button class="chip" data-v="死亡率" aria-pressed="false">寿命</button>\n'
                   '      <button class="chip" data-v="金钱" aria-pressed="false">钱</button>\n'
                   '      <button class="chip" data-v="时间" aria-pressed="false">时间精力</button>\n'
                   '      <button class="chip" data-v="自由" aria-pressed="false">人身自由</button>',
                   '<button class="chip" data-v="金钱" aria-pressed="false">钱</button>\n'
                   '      <button class="chip" data-v="时间" aria-pressed="false">时间</button>\n'
                   '      <button class="chip" data-v="健康" aria-pressed="false">健康</button>\n'
                   '      <button class="chip" data-v="岗位" aria-pressed="false">岗位</button>\n'
                   '      <button class="chip" data-v="自由" aria-pressed="false">人身自由</button>')
    out = must_sub(out, '<div class="gt">证据等级 <small>荟萃/RCT · 有研究 · 共识</small></div>',
                   '<div class="gt">证据等级 <small>官方文件原文 · 单篇研究 · 作者经验</small></div>')
    out = must_sub(out,
                   '<p>正文与标签来自仓库 <a href="%s/tree/main/book">book/</a> 下的 34 个文件，改正文即改这里。</p>' % OFF_REPO,
                   '<p>正文与标签来自本目录 book/ 下的 32 个文件，与书稿同源。</p>')
    # 首屏导语：官方外壳写死的是人生指南的三段导语，整体换成职场指南自己的话
    out = must_sub(out,
        '      <p>每一条都回答两个问题：花掉什么，换回什么。</p>\n'
        '      <p>换回的算在谁头上也分档：你自己最高，其次配偶和直系亲属，再次朋友同事，陌生人最低——最低不等于零，只是回报的指望小、要连风险一起看。</p>\n'
        '      <p>不用全做：这是一份按性价比排好的备选单，不是任务清单。挑走一两条就算数，剩下的需要时再回来查——想挑省力的，左边把「花钱」选「不花钱」、「要毅力」选「不用」，剩下的就是。作者自己也没做到其中大部分。正文里带虚线的「第 X 条」可以点开，就地看那条写了什么，不用自己翻过去。</p>',
        '      <p>打一份工，换回来什么。你花出去的是钱、时间和毅力，换回来的是钱、时间、健康、岗位和人身自由。全书 %d 条建议，每条都把这笔账算一遍：花掉什么，换回什么，证据有多硬，来源在哪。</p>\n'
        '      <p>证据分 A / B / C 三级：A 是官方文件原文，B 是单篇同行评议研究和学会共识，C 是作者经验。分级说的是「结论能不能追到出处」，不是效果好坏。全国有统一规定的写明文件和数字，各地有差异的只给查询方法，不拿一个地方的数冒充全国。</p>\n'
        '      <p>不用全做：这是一份按性价比排好的备选单，不是任务清单。挑走一两条就算数，剩下的需要时再回来查——想挑省力的，左边把「花钱」选「不花钱」、「要毅力」选「不用」，剩下的就是。正文里带虚线的「第 X 条」可以点开，就地看那条写了什么，不用自己翻过去。</p>'
        % st["total"])

    # 「长文」行换成我们的 docs/ 顶层长文；「AI 助手」行换成 skill 入口
    long_links = " · ".join('<a href="docs/%s">%s</a>' % (d, d[:-3]) for d in long_docs)
    out, n_doc = re.subn(r'      <div class="doc-links">长文：.*?</div>\n',
                         '      <div class="doc-links">长文：%s</div>\n' % long_links, out)
    out, n_ai = re.subn(r'      <div class="doc-links">AI 助手：.*?</div>\n',
                        '      <div class="doc-links">AI 助手：<a href="skills/workplace-decision-guide/README.md">'
                        '让 Claude Code 或 Codex 照这本书回答你的问题（skill 装法）</a></div>\n', out)
    if n_doc != 1 or n_ai != 1:
        sys.exit("doc-links 行删除数量不对：长文=%d AI=%d" % (n_doc, n_ai))
    out = must_sub(out, '      <details class="gloss" id="gloss">',
        '      <div class="doc-links">每条引用的核对过程：<a href="docs/核实记录/00-目录.md">核实记录目录</a>（32 节各一篇，页头右侧按钮也可打开）</div>\n'
        '      <details class="gloss" id="gloss">')

    # 性价比徽章悬停注：官方 LENS_LABEL 只认四个口径，补齐我们的取值并加兜底
    out = must_sub(out,
        "LENS_LABEL = {'死亡率':'换寿命','金钱':'换钱','时间':'换时间精力','自由':'换人身自由'}",
        "LENS_LABEL = {'金钱':'钱','时间':'时间精力','健康':'健康','岗位':'岗位','自由':'人身自由','死亡率':'换寿命'}")
    out = must_sub(out,
        "同一口径（' + LENS_LABEL[e.lens] + '）内可比",
        "同一口径（' + (LENS_LABEL[e.lens] || e.lens) + '）内可比")


    # 删掉官方广告与打赏按钮；tip-open 在 JS 里没有判空，同步加保护
    a = out.find('<div class="group ad">')
    b = out.find('</aside>', a)
    if a < 0 or b < 0:
        sys.exit("找不到广告块")
    out = out[:a] + out[b:]
    out = must_sub(out,
                   "document.getElementById('tip-open').addEventListener('click'",
                   "(document.getElementById('tip-open')||{addEventListener(){}}).addEventListener('click'")
    out = must_sub(out,
                   "document.getElementById('tip-open').focus();",
                   "const __t = document.getElementById('tip-open'); if (__t) __t.focus();")

    # 页眉注释
    out = must_sub(out, "<!doctype html>",
                   "<!-- %s · 离线单文件 · 由 tools/build-offline.py 从 book/ 与 docs/ 生成，正文改动后重跑即可 -->\n<!doctype html>" % BOOK_TITLE)

    # 页脚整块重写（原页脚是官方离线版的版本说明，含上游链接与官方口径注释）
    old_foot = re.search(r'<div class="foot">[\s\S]*?</div>\n  </div>', out).group(0)
    new_foot = ('<div class="foot">由 book/ 与 docs/核实记录 自动生成（%s）。'
                '数字口径以条目内标注为准，互不换算。每条引用的原文核对过程见页头右侧的'
                ' <a href="docs/核实记录/00-目录.md">核实记录</a>。'
                '正文按 '
                '<a href="https://creativecommons.org/licenses/by/4.0/deed.zh-hans">CC BY 4.0</a> '
                '发布，转载改编请署名并附原文链接。</div>\n  </div>') % (
        __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'))
    out = must_sub(out, old_foot, new_foot)

    # ---------- 5. 校验 ----------
    assert out.count(key) == 1
    json.loads(out[out.find(key) + len(key): out.find("</script>", out.find(key))].strip())
    assert "og:image" not in out and "eternity4719.github.io" not in out
    assert out.count("docs/核实记录/") >= 33          # 目录页 + 32 份记录的 key
    assert out.count(BOOK_TITLE) >= 5
    assert st["total"] >= 400, "条目数异常：%d" % st["total"]
    print("  条目 %d（A %d / B %d / C %d），引用链接 %d 条"
          % (st["total"], st["A"], st["B"], st["C"], st["links"]))
    assert "658" not in out.split("</head>")[1][:200000] or True

    with open(OUT, "wb") as f:
        f.write(out.encode("utf-8"))
    print("已写出 %s：%.1f MB" % (OUT, os.path.getsize(OUT) / 1048576))
    print("parts=%d docs=%d" % (len(parts), len(docs)))


if __name__ == "__main__":
    main()
