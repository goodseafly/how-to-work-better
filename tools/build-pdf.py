# -*- coding: utf-8 -*-
"""
按官方 HowToLiveBetter 的 PDF 排版链生成《高性价比职场指南》PDF。

官方链路：tools/pdf/build.mjs —— 把 README + book/*.md + docs/*.md 拼成一本 Markdown，
pandoc（gfm+attributes → typst，套 tools/pdf/template.typ 模板）转成 typst，typst 排版出 PDF。
版面三件事在模板里定死：封面（og.png + 副标题）、目录、正文（一级标题另起一页、页眉书名+节名、页脚页码）。

本脚本用 Python 复刻同一条链路，逻辑与官方 build.mjs 一致，另有四处适配：
- 书名、描述、版本说明换成职场书的；
- 附录直接取 docs/核实记录/*.md（官方是从 README 链接里发现的，我们的 README 没链它们）；
- front matter 里的 <details> 展开成正文（pandoc 会把整块 raw HTML 丢掉，术语表会跟着丢）；
- 全书的「第 X 节第 Y 条（词）/ 本节第 Y 条（词）/ 第 X 节（词）」交叉引用自动变成
  书内跳转链接（每条目挂 {#e-节-条} 锚点，官方检索页的 xref 行为搬进 PDF；官方 PDF 里这些是死文字）。

封面 og.png 按官方 og 的版式重画：浅色渐变底、左上小徽标、两行大标题（换回的关键词用蓝）、
灰色领域行、一排数据胶囊。文案素材全部取自 README 首段，不发明新说法。

依赖：pandoc 3.12、typst 0.15.1。按「PANDOC / TYPST 环境变量 → 同目录的
local_paths.py（本机私有，不进仓库）→ PATH → 裸命令名」的顺序找，CI 上靠 PATH 命中。

用法：python tools/build-pdf.py
"""
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("BOOK_OUT") or os.path.dirname(ROOT)
OUT_PDF = os.path.join(OUT_DIR, "高性价比职场指南.pdf")
def _local(name):
    """本机私有路径：同目录的 local_paths.py（不进仓库）。"""
    try:
        import local_paths
    except Exception:
        return None
    return getattr(local_paths, name, None)


def _tool(env, exe):
    """环境变量 → 本机私有配置 → PATH → 裸命令名；CI 上靠 PATH 命中。"""
    return os.environ.get(env) or _local(env) or shutil.which(exe) or exe


PANDOC = _tool("PANDOC", "pandoc")
TYPST = _tool("TYPST", "typst")
WORK = os.path.join(ROOT, "_pdf_build")
OFFICIAL_TEMPLATE = os.path.join(HERE, "template.typ")

def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


# 封面要用的中文字体：Windows 上是微软雅黑，Linux / CI 上是 Noto CJK。
_WIN_BOLD = r"C:/Windows/Fonts/msyhbd.ttc"
_WIN_REG = r"C:/Windows/Fonts/msyh.ttc"
_NIX_BOLD = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
             "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"]
_NIX_REG = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]
CJK_REG = (_first_existing([_WIN_REG] + _NIX_REG)
           or _first_existing([_WIN_BOLD] + _NIX_BOLD))
CJK_BOLD = _first_existing([_WIN_BOLD] + _NIX_BOLD) or CJK_REG
if not CJK_REG:
    raise SystemExit(
        "找不到中文字体。Linux 上装 fonts-noto-cjk，或把字体路径加进 "
        "tools/build-pdf.py 顶部的 _NIX_REG / _NIX_BOLD 候选列表。")

BOOKTITLE = "高性价比职场指南"
AUTHOR = "guhaifei"
# 副标题里的条目数由 book/ 现算（见 book_stats），改正文后不用回来改这里
SUBTITLE_TPL = ("按性价比排序的职场指南：%d 条建议，每条写明成本、收益、证据等级和原始出处，"
                "可按钱、时间、毅力、收益、口径五个维度检索。")
STAMP = datetime.now().strftime("%Y-%m-%d %H:%M")
OFF_REPO = "https://github.com/eternity4719/HowToLiveBetter"


def read(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8")


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(text.encode("utf-8"))


# ---------- 封面 og.png（官方 og 同版式：浅渐变底 + 小徽标 + 两行大标题 + 领域行 + 胶囊行） ----------
def make_og():
    p = os.path.join(ROOT, "og.png")
    if os.path.exists(p):
        print("  og.png 已存在，跳过封面重画（改过条目数要重画，先删掉它）")
        return
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    W, H = 1200, 630
    BLUE, DARK, GRAY = "#3451b2", "#1c1b19", "#5f6672"
    img = Image.new("RGB", (W, H), "#ffffff")

    # 浅色渐变底：左上淡蓝、右下淡绿两团柔光，近似官方 og 的底色
    glow = Image.new("RGB", (W, H), "#ffffff")
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-360, -300, 560, 260], fill="#dfe9fb")
    gd.ellipse([700, 380, 1500, 900], fill="#def0e4")
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    img = Image.blend(img, glow, 0.85)
    d = ImageDraw.Draw(img)

    def fit(text, path, size, max_w):
        f = ImageFont.truetype(path, size)
        while d.textlength(text, font=f) > max_w and size > 12:
            size -= 2
            f = ImageFont.truetype(path, size)
        return f

    MAXW = W - 160
    FB, FR = CJK_BOLD, CJK_REG
    fb96 = fit("换回钱、时间、健康、岗位和自由", FB, 76, MAXW)
    fb34 = ImageFont.truetype(FB, 30)
    fm34 = fit("投简历 · 劳动合同 · 工资工时 · 社保公积金 · 生病生育 · 维权仲裁 · 裁员跳槽 · 养老",
               FR, 34, MAXW)

    # 左上：蓝底白勾小徽标 + 书名
    x, y, s = 80, 58, 46
    d.rounded_rectangle([x, y, x + s, y + s], radius=11, fill=BLUE)
    d.line([(x + 12, y + 24), (x + 20, y + 33), (x + 35, y + 13)],
           fill="white", width=7, joint="curve")
    d.text((x + s + 16, y + 4), BOOKTITLE, font=fb34, fill=DARK)

    # 两行大标题：换回的关键词用蓝（文案取自 README 首段）
    l1 = "花出去的是钱、时间和毅力，"
    l2a, l2b = "换回", "钱、时间、健康、岗位和自由"
    d.text((78, 152), l1, font=fb96, fill=DARK)
    w1 = d.textlength(l2a, font=fb96)
    d.text((78, 256), l2a, font=fb96, fill=DARK)
    d.text((78 + w1, 256), l2b, font=fb96, fill=BLUE)

    # 灰色领域行
    d.text((82, 388), "投简历 · 劳动合同 · 工资工时 · 社保公积金 · 生病生育 · 维权仲裁 · 裁员跳槽 · 养老",
           font=fm34, fill=GRAY)

    # 胶囊行：数字加粗、底色淡彩，与官方 og 同款；数字全部现算，不写死
    _book = os.path.join(ROOT, "book")
    _tot, _nA, _nB, _nC, _nl = book_stats(
        [os.path.join(_book, f) for f in sorted(os.listdir(_book)) if f.endswith(".md")])
    badges = [("%d 条建议" % _tot, BLUE, "#e3ebfa"),
              ("A 级 %d · B 级 %d · C 级 %d" % (_nA, _nB, _nC), "#18794e", "#def0e2"),
              ("%d 条原文链接" % _nl, DARK, "#eef0f3"),
              ("可按五维筛选", DARK, "#eef0f3")]
    # 胶囊行整排放不下就整体缩字号
    bs = 30
    while True:
        widths = [d.textlength(t, font=ImageFont.truetype(FB, bs)) for t, _, _ in badges]
        total = sum(w + 60 for w in widths) + 22 * (len(badges) - 1)
        if total <= MAXW or bs <= 14:
            break
        bs -= 2
    fsb = ImageFont.truetype(FB, bs)
    bx, by, bh, pad = 80, 476, 64, 30
    for text, fg, bg in badges:
        w = d.textlength(text, font=fsb)
        d.rounded_rectangle([bx, by, bx + w + pad * 2, by + bh], radius=bh // 2, fill=bg)
        d.text((bx + pad, by + (bh - bs) // 2 - 2), text, font=fsb, fill=fg)
        bx += w + pad * 2 + 22
    img.save(p)
    print("封面 og.png 已生成（官方 og 同版式）")


# ---------- README 结构解析（与官方 lib/book.mjs 同逻辑） ----------
def book_stats(abs_paths):
    """从 book/*.md 现算条目数、A/B/C 分布、去重后的引用链接数。"""
    from collections import Counter
    grades, links, total = Counter(), set(), 0
    for p in abs_paths:
        md = read(p)
        total += len(re.findall(r"^### \d+\. ", md, re.M))
        for m in re.finditer(r"^- 证据等级：\s*([ABC])\s*$", md, re.M):
            grades[m.group(1)] += 1
        links.update(re.findall(r"<(https?://[^>\s]+)>", md))
    n = sum(grades.values())
    if total != n:
        sys.exit("条目 %d 与证据等级合计 %d 对不上" % (total, n))
    return total, grades["A"], grades["B"], grades["C"], len(links)


def read_book():
    readme = read(os.path.join(ROOT, "README.md")).replace("\r\n", "\n")
    lines = readme.split("\n")

    def between(a, b):
        ia = next(i for i, l in enumerate(lines) if l.startswith(a))
        ib = next(i for i, l in enumerate(lines) if i > ia and l.startswith(b))
        return "\n".join(lines[ia:ib])

    front_md = between("## 这本书想回答的问题", "## 目录")
    contents_md = between("## 目录", "## 章节之间怎么分工")
    book_files = sorted(set(m.group(1) for m in
                            re.finditer(r"\]\((book/[^)#]+\.md)\)", contents_md)))
    if len(book_files) != 32:
        sys.exit("目录里发现 %d 个 book 文件，应为 32" % len(book_files))
    doc_dir = os.path.join(ROOT, "docs", "核实记录")
    doc_files = ["docs/核实记录/" + f for f in sorted(os.listdir(doc_dir))
                 if f.endswith(".md") and not f.startswith("00-")]
    long_docs = ["docs/" + f for f in sorted(os.listdir(os.path.join(ROOT, "docs")))
                 if f.endswith(".md") and os.path.isfile(os.path.join(ROOT, "docs", f))]
    return readme, front_md, contents_md, book_files, doc_files, long_docs


# ---------- 链接改写（与官方 build.mjs 同逻辑） ----------
def rewrite_links(md, src, anchor_of):
    def repl(m):
        href, title = m.group(1), m.group(2) or ""
        if href.startswith(("http:", "https:", "mailto:")):
            return m.group(0)
        if href.startswith("#"):
            return "](%s/blob/main/README.md%s%s)" % (OFF_REPO, href, title)
        path = href.split("#")[0]
        base = os.path.dirname(src).replace("\\", "/")
        target = os.path.normpath(os.path.join(base, path)).replace("\\", "/")
        if target in anchor_of:
            return "](#%s%s)" % (anchor_of[target], title)
        kind = "tree" if target.endswith("/") else "blob"
        return "](%s/%s/main/%s%s)" % (OFF_REPO, kind, target, title)
    return re.sub(r"\]\(([^)\s]+)(\s+\"[^\"]*\")?\)", repl, md)


def strip_backlink(md):
    return re.sub(r"^\[← 回总目录\]\([^)]*\)\s*\n", "", md)


# ---------- 交叉引用变成书内跳转（官方检索页的 xref 行为，这里搬进 PDF） ----------
# 三种写法与 tools/check-refs.py 的审计口径一致：第 X 节第 Y 条（词）/ 本节第 Y 条（词）/ 第 X 节（词）。
# 法条引用全用汉字数字（「第二百五十三条」），不会被这些数字模式误伤；
# 附录核实记录里的「第 N 条（词）」指向本节条目，同样成立。
PAREN = r"[（(][^）)]{1,30}[）)]"


def linkify_xrefs(md, cur, valid):
    def sec_item(m):
        x, y = int(m.group(1)), int(m.group(2))
        return "[%s](#e-%d-%d)" % (m.group(0), x, y) if y in valid.get(x, ()) else m.group(0)

    def this_item(m):
        y = int(m.group(1))
        return "[%s](#e-%d-%d)" % (m.group(0), cur, y) if y in valid.get(cur, ()) else m.group(0)

    def sec_only(m):
        x = int(m.group(1))
        return "[%s](#sec-%d)" % (m.group(0), x) if 1 <= x <= 32 else m.group(0)

    md = re.sub(r"第\s?(\d+)\s?节\s?第\s?(\d+)\s?条\s?" + PAREN, sec_item, md)
    if cur:
        md = re.sub(r"本节\s?第\s?(\d+)\s?条\s?" + PAREN, this_item, md)
    md = re.sub(r"第\s?(\d+)\s?节\s?" + PAREN, sec_only, md)
    return md


def main():
    make_og()
    readme, front_md, contents_md, book_files, doc_files, long_docs = read_book()
    n_tot, n_A, n_B, n_C, n_links = book_stats([os.path.join(ROOT, f) for f in book_files])
    subtitle = SUBTITLE_TPL % n_tot
    print("  条目 %d（A %d / B %d / C %d），引用链接 %d 条"
          % (n_tot, n_A, n_B, n_C, n_links))

    anchor_of = {}
    valid = {}
    for f in book_files:
        n = int(re.match(r"(\d+)", os.path.basename(f)).group(1))
        anchor_of[f] = "sec-%d" % n
        text = strip_backlink(read(os.path.join(ROOT, f)))
        valid[n] = set(int(m) for m in re.findall(r"^### (\d+)\.", text, re.M))
    for i, f in enumerate(long_docs, 1):
        anchor_of[f] = "long-%d" % i
    for i, f in enumerate(doc_files, 1):
        anchor_of[f] = "doc-%d" % i

    # front matter 里的 <details> 展开掉，否则 pandoc 把整块 raw HTML 丢掉，术语表会跟着丢
    front_md = re.sub(r"<details>\s*\n<summary>[^<]*</summary>\s*", "", front_md)
    front_md = front_md.replace("</details>", "")

    about = """# 版本说明

这本 PDF 由本目录的 Markdown 正文自动排版，正文一改就重新排一本。手里这本的版本：

- 生成时间：%s（北京时间）
- 在线检索页：同目录的《高性价比职场指南-全本.html》（按关键词、章节、证据等级和成本筛选）
- 体例来源：HowToLiveBetter（CC BY 4.0，%s）

正文里指向书内其他节的链接、以及全部「第 X 节第 Y 条」交叉引用，都做成了书内跳转；每节正文后面跟着该节的核实记录（引用原文的逐条核对过程）。

正文按 CC BY 4.0 发布（https://creativecommons.org/licenses/by/4.0/）。可以转载、改编、商用，要写明出处「%s」，改过内容的要注明改过。
""" % (STAMP, OFF_REPO, BOOKTITLE)

    pages = [
        {"src": "README.md", "anchor": "front",
         "md": "# 前言\n\n%s\n\n%s" % (subtitle, front_md)},
        {"src": "README.md", "anchor": "contents",
         "md": contents_md.replace("## 目录", "# 各节简介", 1)},
    ]
    pages += [{"src": f, "anchor": anchor_of[f], "md": strip_backlink(read(os.path.join(ROOT, f)))}
              for f in book_files]
    pages += [{"src": f, "anchor": anchor_of[f], "md": strip_backlink(read(os.path.join(ROOT, f)))}
              for f in long_docs]
    pages += [{"src": f, "anchor": anchor_of[f], "md": strip_backlink(read(os.path.join(ROOT, f)))}
              for f in doc_files]
    pages.append({"src": "README.md", "anchor": "about", "md": about})

    n_xref = 0
    body_parts = []
    for p in pages:
        md = rewrite_links(p["md"], p["src"], anchor_of)
        md = re.sub(r"<!--[\s\S]*?-->", "", md)                      # 成本标签注释不进 PDF
        # 条目标题挂锚点 {#e-节-条}，供交叉引用跳转
        m = re.match(r"book/(\d+)-", p["src"])
        if m:
            n = int(m.group(1))
            md = re.sub(r"^(### (\d+)\. .+?)\s*$",
                        lambda mm: "%s {#e-%d-%s}" % (mm.group(1), n, mm.group(2)),
                        md, flags=re.M)
        md = linkify_xrefs(md, n if m else None, valid)
        n_xref += len(re.findall(r"\]\(#e-\d+-\d+\)", md)) + len(re.findall(r"\]\(#sec-\d+\)", md))
        md = re.sub(r"^(# .+?)\s*$", r"\1 {#%s}" % p["anchor"], md, count=1, flags=re.M)
        if "{#%s}" % p["anchor"] not in md:
            sys.exit("%s 挂不上锚点 %s" % (p["src"], p["anchor"]))
        body_parts.append(md.strip())
    body = "\n\n".join(body_parts)
    print("交叉引用已转为书内跳转：%d 处" % n_xref)

    body_md = os.path.join(WORK, "book.md")
    write(body_md, body)

    # 模板：官方 template.typ 原样取用，只把封面尾注换成职场书的说法
    tpl = read(OFFICIAL_TEMPLATE)
    tpl = tpl.replace('author: "eternity4719"', 'author: "%s"' % AUTHOR)
    tpl = tpl.replace(
        "生成于 $builddate$（北京时间）　·　正文提交 $commit$ \\\n"
        "    正文每天都在改，以在线版为准：$site$ \\\n"
        "    在线检索、EPUB 与本 PDF 的最新版都在 $repo$",
        "生成于 $builddate$（北京时间） \\\n"
        "    在线检索页：同目录《高性价比职场指南-全本.html》 \\\n"
        "    体例继承 HowToLiveBetter（CC BY 4.0）")
    if "$site$" in tpl or "$repo$" in tpl or "$commit$" in tpl:
        sys.exit("模板里还残留 site/repo/commit 变量引用，检查封面块是否匹配")
    tpl_path = os.path.join(WORK, "template.typ")
    write(tpl_path, tpl)

    typ_file = os.path.join(WORK, "book.typ")
    subprocess.run([PANDOC, "--from=gfm+attributes", "--to=typst", "--wrap=none",
                    "--template=" + tpl_path,
                    "-V", "booktitle=" + BOOKTITLE,
                    "-V", "subtitle=" + subtitle,
                    "-V", "builddate=" + STAMP,
                    "-o", typ_file, body_md],
                   check=True, cwd=ROOT, capture_output=True, text=True)
    print("pandoc 完成：%s（%d 字节）" % (typ_file, os.path.getsize(typ_file)))

    r = subprocess.run([TYPST, "compile", "--root", ROOT, typ_file, OUT_PDF],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("typst 失败：\n" + (r.stderr or r.stdout)[-3000:])
    if r.stdout.strip():
        print(r.stdout.strip())
    n_items = sum(1 for l in body.split("\n") if l.startswith("### ") and "{#e-" in l)
    print("已生成 %s：%.1f MB，%d 节 %d 条，附录 %d 篇"
          % (OUT_PDF, os.path.getsize(OUT_PDF) / 1048576, len(book_files), n_items, len(doc_files)))


if __name__ == "__main__":
    main()
