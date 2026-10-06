# -*- coding: utf-8 -*-
"""生成《高性价比职场指南》EPUB 3 电子书。

结构与官方 HowToLiveBetter.epub 对齐：
  cover.xhtml    封面（og.png 拷成包内的 cover.png）
  front.xhtml    前言（README 的 H1 与首段 + 「## 这本书想回答的问题」到「## 目录」之前）
  contents.xhtml 各节简介（README 的「## 目录」整段）
  ch01..ch32     book/*.md 正文 32 节
  doc1..doc3     docs/*.md 长文
  about.xhtml    版本说明
另附 toc.ncx，给只认 EPUB 2 的阅读器兜底；目录按 h1/h2/h3 分两层。

只依赖 pandoc 做 md→html；zip 用标准库手写（EPUB 要求 mimetype 是第一个条目且不压缩）。

用法：
  python tools/build-epub.py
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

def _local(name):
    """本机私有路径：同目录的 local_paths.py（不进仓库）。"""
    try:
        import local_paths
    except Exception:
        return None
    return getattr(local_paths, name, None)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANDOC = (os.environ.get("PANDOC") or _local("PANDOC")
          or shutil.which("pandoc") or "pandoc")
OUT_DIR = os.environ.get("BOOK_OUT") or os.path.dirname(ROOT)
os.makedirs(OUT_DIR, exist_ok=True)  # CI 里 BOOK_OUT=dist 时目录尚不存在
OUT = os.path.join(OUT_DIR, "高性价比职场指南.epub")
OG = os.path.join(ROOT, "og.png")
TITLE = "高性价比职场指南"
SUBTITLE = "打一份工，换回来什么"
CREATOR = "seafly"
REPO = "https://github.com/eternity4719/HowToLiveBetter"

CSS = """body{font-family:"Source Han Serif SC","Noto Serif CJK SC",serif;line-height:1.75;margin:0;padding:0 4%}
h1{font-size:1.5em;margin:1.2em 0 .6em;line-height:1.4}
h2{font-size:1.25em;margin:1.4em 0 .5em}
h3{font-size:1.08em;margin:1.6em 0 .4em;line-height:1.5}
ul,ol{padding-left:1.4em}li{margin:.35em 0}
table{border-collapse:collapse;margin:1em 0;width:100%;font-size:.92em}
th,td{border:1px solid #bbb;padding:.35em .5em;text-align:left}
code{font-size:.9em;background:#f2f2f2;padding:0 .25em}
a{color:#3451b2;text-decoration:none}
.back{color:#888;font-size:.9em}
.cover{margin:0;padding:0;text-align:center}
.cover img{max-width:100%;height:auto}
"""
# 封面页单独用一版不留白边的样式
CSS_COVER = CSS + "body{margin:0;padding:0}\n.cover{display:block}\n"


def read(p):
    return open(p, "rb").read().decode("utf-8")


def pandoc_html(md_text):
    p = subprocess.run([PANDOC, "--from=gfm", "--to=html", "--wrap=none"],
                       input=md_text.encode("utf-8"), capture_output=True)
    if p.returncode != 0:
        sys.exit("pandoc 失败：" + (p.stderr or b"").decode("utf-8", "replace")[:800])
    return p.stdout.decode("utf-8")


def rewrite_links(html, doc_map):
    """book/NN-x.md → chNN.xhtml；docs/NAME.md → docN.xhtml；核实记录与本地非页面链接降级成纯文本。"""
    def book_repl(m):
        return 'href="ch%02d.xhtml"' % int(m.group(1))
    html = re.sub(r'href="book/(\d+)-[^"]*\.md"', book_repl, html)

    def doc_repl(m):
        return 'href="%s"' % doc_map.get(m.group(1), "#")
    html = re.sub(r'href="docs/([^/"]+\.md)"', doc_repl, html)
    # 核实记录、skills 等没有对应页面的链接：拆掉 <a> 保留文字
    html = re.sub(r'<a href="(?:docs/核实记录|skills)[^"]*">([^<]*)</a>', r"\1", html)
    # 相对路径残余（../README.md 等）
    html = re.sub(r'<a href="\.\./[^"]*">([^<]*)</a>', r"\1", html)
    return html


def xhtml_page(title, body, css="style.css"):
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            'xml:lang="zh-CN" lang="zh-CN">\n<head>\n<meta charset="utf-8"/>\n'
            '<title>%s</title>\n<link rel="stylesheet" type="text/css" href="%s"/>\n'
            '</head>\n<body>\n%s\n</body>\n</html>\n' % (title, css, body))


SEQ = [0]


def add_heading_ids(html):
    """给 h1..h3 换成本书自己的顺序 id，并记下 (id, 层级, 纯文字)，供目录用。

    注意：pandoc 的 HTML 输出默认带 auto_identifiers，标题上已经有 id（而且是中文的），
    所以模式里必须容忍 `<h2 id="...">` 这种形态，否则一条都匹配不上、目录里全是空的。
    """
    heads = []

    def repl(m):
        depth = int(m.group(1))
        inner = m.group(2)
        SEQ[0] += 1
        hid = "h%d" % SEQ[0]
        heads.append((hid, depth, re.sub(r"<[^>]+>", "", inner).strip()))
        return '<h%d id="%s">%s</h%d>' % (depth, hid, inner, depth)

    html = re.sub(r"<h([1-3])(?:\s[^>]*)?>(.*?)</h\1>", repl, html, flags=re.S)
    return html, heads


def head_description(readme):
    """从 README 头部取首段导语（跳过 HTML 块、H1、徽章行），不另写一份免得两边不一致。"""
    head = readme[: readme.find("\n## ")]
    for block in (b.strip() for b in head.split("\n\n")):
        if not block:
            continue
        if block.startswith(("<", "#", "[!", "###", "|", "<table")):
            continue
        return block.replace("<br>", "").replace("\n", "")
    return ""


def book_stats():
    """从 book/ 现算条目数与 A/B/C，用于版本说明页。"""
    grades = {"A": 0, "B": 0, "C": 0}
    total = 0
    for p in glob.glob(os.path.join(ROOT, "book", "*.md")):
        for line in read(p).splitlines():
            if re.match(r"^### \d+\. ", line):
                total += 1
            m = re.match(r"^- 证据等级：\s*([ABC])", line)
            if m:
                grades[m.group(1)] += 1
    return total, grades


def about_md(total, grades):
    stamp = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    return (
        "# 版本说明\n\n"
        "这本电子书由仓库里的 Markdown 正文自动生成，正文一改就重新生成一本。手里这本的版本：\n\n"
        "- 生成时间：%s（北京时间）\n"
        "- 条目：%d 条（A %d / B %d / C %d）\n"
        "- 在线检索页、离线单文件、PDF、EPUB 四样，都由 tools/ 下的脚本从 book/ 里的正文现生成\n"
        "- 每条来源的核实记录：docs/核实记录/\n"
        "- 体例来源与查看器外壳：[HowToLiveBetter](%s)（CC BY 4.0）\n\n"
        "正文里指向仓库内其他文件的链接已改成书内跳转。\n\n"
        "正文以 CC BY 4.0 发布（https://creativecommons.org/licenses/by/4.0/）。"
        "可以转载、改编、商用，要写明出处「高性价比职场指南」并附仓库链接，改过内容的要注明改过。"
        "书里的法条、社保比例、假期天数和各项标准经常更新，转载时请同时写上你同步的是哪一天的版本。\n"
        % (stamp, total, grades["A"], grades["B"], grades["C"], REPO)
    )


def main():
    readme = read(os.path.join(ROOT, "README.md"))

    # ---------- 切 README ----------
    # front = 「## 这本书想回答的问题」→「## 目录」之前（跟官方 lib/book.mjs 同一算法，不含网页头部）
    m_h1 = re.search(r"(?m)^## 这本书想回答的问题\s*$", readme)
    m_toc = re.search(r"(?m)^## 目录\s*$", readme)
    if not m_h1 or not m_toc:
        sys.exit("README 里找不到「## 这本书想回答的问题」或「## 目录」")
    front_md = readme[m_h1.start(): m_toc.start()].rstrip()
    rest = readme[m_toc.start():]
    m_next = re.search(r"(?m)^## (?!目录)", rest[3:])
    toc_md = rest[: m_next.start() + 3].rstrip() if m_next else rest.rstrip()
    toc_md = toc_md.replace("## 目录", "# 各节简介", 1)
    desc = head_description(readme)

    total, grades = book_stats()

    # ---------- 页面清单 ----------
    book_files = sorted(glob.glob(os.path.join(ROOT, "book", "*.md")),
                        key=lambda p: int(re.match(r"(\d+)-", os.path.basename(p)).group(1)))
    doc_files = sorted(glob.glob(os.path.join(ROOT, "docs", "*.md")))
    doc_map = {os.path.basename(p): "doc%d.xhtml" % (i + 1) for i, p in enumerate(doc_files)}

    pages = []
    cover_body = '<div class="cover"><img src="cover.png" alt="%s"/></div>' % TITLE
    pages.append({"file": "cover.xhtml", "title": "封面", "body": cover_body, "heads": [], "cover": True})

    front_body = rewrite_links(
        pandoc_html("# %s\n\n**%s**\n\n%s\n\n%s" % (TITLE, SUBTITLE, desc, front_md)), doc_map)
    pages.append({"file": "front.xhtml", "title": "前言", "body": front_body})

    pages.append({"file": "contents.xhtml", "title": "各节简介",
                  "body": rewrite_links(pandoc_html(toc_md), doc_map)})

    for i, p in enumerate(book_files):
        text = read(p)
        text = re.sub(r"(?m)^\[← 回总目录\]\(\.\./README\.md\)\s*\n", "", text)
        html = rewrite_links(pandoc_html(text), doc_map)
        m = re.search(r"^# (\d+)\. (.+?)\s*$", text, re.M)
        pages.append({"file": "ch%02d.xhtml" % (i + 1),
                      "title": "%s. %s" % (m.group(1), m.group(2)), "body": html})

    for i, p in enumerate(doc_files):
        text = read(p)
        text = re.sub(r"(?m)^\[← 回总目录\]\(\.\./README\.md\)\s*\n", "", text)
        html = rewrite_links(pandoc_html(text), doc_map)
        m = re.search(r"^# (.+?)\s*$", text, re.M)
        pages.append({"file": "doc%d.xhtml" % (i + 1), "title": m.group(1), "body": html})

    pages.append({"file": "about.xhtml", "title": "版本说明",
                  "body": rewrite_links(pandoc_html(about_md(total, grades)), doc_map)})

    # ---------- 补 heading id，收目录 ----------
    for p in pages:
        if p.get("cover"):
            p["heads"] = []
            continue
        p["body"], p["heads"] = add_heading_ids(p["body"])

    nav_items = []
    for p in pages:
        heads = p["heads"]
        first = heads[0] if heads else None
        if first and first[1] == 1:
            top = (p["file"] + "#" + first[0], p["title"])
            rest_h = heads[1:]
        else:
            top = (p["file"], p["title"])
            rest_h = heads
        subs = [(p["file"] + "#" + h[0], h[2]) for h in rest_h if h[1] <= 3]
        nav_items.append((top, subs))

    def nav_li(item):
        (href, text), subs = item
        out = '<li><a href="%s">%s</a>' % (href, text)
        if subs:
            out += "\n<ol>\n" + "\n".join(
                '<li><a href="%s">%s</a></li>' % s for s in subs) + "\n</ol>\n"
        return out + "</li>"

    nav = xhtml_page("目录",
                     '<nav epub:type="toc" id="toc">\n<h1>目录</h1>\n<ol>\n%s\n</ol>\n</nav>\n'
                     '<nav epub:type="landmarks" hidden="hidden">\n<ol>\n'
                     '<li><a epub:type="cover" href="cover.xhtml">封面</a></li>\n'
                     '<li><a epub:type="bodymatter" href="front.xhtml">正文</a></li>\n'
                     '</ol>\n</nav>' % "\n".join(nav_li(i) for i in nav_items))

    # ---------- toc.ncx（EPUB 2 兜底） ----------
    book_id = "urn:uuid:%s" % uuid.uuid5(uuid.NAMESPACE_URL, "workplace-guide-zh-cn")
    play = [0]

    def nav_point(item):
        (href, text), subs = item
        play[0] += 1
        n = play[0]
        return ('<navPoint id="np%d" playOrder="%d"><navLabel><text>%s</text></navLabel>'
                '<content src="%s"/>%s</navPoint>'
                % (n, n, text, href, "".join(nav_point1(s) for s in subs)))

    def nav_point1(sub):
        play[0] += 1
        n = play[0]
        return ('<navPoint id="np%d" playOrder="%d"><navLabel><text>%s</text></navLabel>'
                '<content src="%s"/></navPoint>' % (n, n, sub[1], sub[0]))

    ncx = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="zh-CN">\n'
           '<head>\n<meta name="dtb:uid" content="%s"/>\n<meta name="dtb:depth" content="2"/>\n'
           '<meta name="dtb:totalPageCount" content="0"/>\n<meta name="dtb:maxPageNumber" content="0"/>\n'
           '</head>\n<docTitle><text>%s</text></docTitle>\n<navMap>\n%s\n</navMap>\n</ncx>\n'
           % (book_id, TITLE, "\n".join(nav_point(i) for i in nav_items)))

    # ---------- content.opf ----------
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = "\n".join('    <item id="p%02d" href="%s" media-type="application/xhtml+xml"/>'
                         % (i, p["file"]) for i, p in enumerate(pages))
    spine = "\n".join('    <itemref idref="p%02d"/>' % i for i in range(len(pages)))
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">\n'
           '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
           '    <dc:identifier id="bookid">%s</dc:identifier>\n'
           '    <dc:title>%s · %s</dc:title>\n'
           '    <dc:language>zh-CN</dc:language>\n'
           '    <dc:creator>%s</dc:creator>\n'
           '    <dc:description>%s</dc:description>\n'
           '    <dc:source>%s</dc:source>\n'
           '    <dc:rights>CC BY 4.0</dc:rights>\n'
           '    <meta property="dcterms:modified">%s</meta>\n'
           '    <meta name="generator" content="tools/build-epub.py"/>\n'
           '  </metadata>\n'
           '  <manifest>\n'
           '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n'
           '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
           '    <item id="css" href="style.css" media-type="text/css"/>\n'
           '    <item id="cover-css" href="cover.css" media-type="text/css"/>\n'
           '    <item id="cover-img" href="cover.png" media-type="image/png" properties="cover-image"/>\n'
           '%s\n  </manifest>\n'
           '  <spine toc="ncx">\n%s\n  </spine>\n'
           '</package>\n'
           % (book_id, TITLE, SUBTITLE, CREATOR, desc.replace("&", "&amp;").replace("<", "&lt;"),
              REPO, now, manifest, spine))

    # ---------- 打包 ----------
    data = {"META-INF/container.xml":
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
            '  <rootfiles>\n    <rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/>\n  </rootfiles>\n</container>\n',
            "OEBPS/style.css": CSS, "OEBPS/nav.xhtml": nav,
            "OEBPS/toc.ncx": ncx, "OEBPS/content.opf": opf}
    for p in pages:
        data["OEBPS/" + p["file"]] = xhtml_page(
            p["title"], p["body"], css="cover.css" if p.get("cover") else "style.css")
    data["OEBPS/cover.css"] = CSS_COVER
    cover_png = open(OG, "rb").read()

    for _ in range(8):
        try:
            os.remove(OUT)
        except FileNotFoundError:
            pass
        try:
            with zipfile.ZipFile(OUT, "w") as z:
                zi = zipfile.ZipInfo("mimetype")
                zi.compress_type = zipfile.ZIP_STORED
                z.writestr(zi, "application/epub+zip")
                for name, content in data.items():
                    z.writestr(name, content)
                z.writestr("OEBPS/cover.png", cover_png)
            ok = os.path.exists(OUT) and zipfile.ZipFile(OUT).namelist()[0] == "mimetype"
            if ok:
                break
        except Exception:
            time.sleep(0.4)
    else:
        sys.exit("EPUB 写出不稳定")

    z = zipfile.ZipFile(OUT)
    nav_x = z.read("OEBPS/nav.xhtml").decode("utf-8")
    print("已写出 %s：%.2f MB，%d 页（封面 + 前言 + 各节简介 + 32 节 + %d 长文 + 版本说明）"
          % (OUT, os.path.getsize(OUT) / 1048576, len(pages), len(doc_files)))
    print("  首项: %s | mimetype 不压缩: %s | 包内 %d 项"
          % (z.namelist()[0], z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED, len(z.namelist())))
    print("  目录：一级 %d 条 / 二级 %d 条 | 封面 %s | toc.ncx %s"
          % (len(nav_items), sum(len(s) for _, s in nav_items),
             "有" if "OEBPS/cover.png" in z.namelist() else "无",
             "有" if "OEBPS/toc.ncx" in z.namelist() else "无"))
    print("  条目 %d（A %d / B %d / C %d）" % (total, grades["A"], grades["B"], grades["C"]))


if __name__ == "__main__":
    main()
