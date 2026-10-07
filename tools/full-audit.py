#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""职场册全文校验（比 check-body / check-refs 更高一层：查的是「产出对齐」）

跑法（在书根目录）：
    python tools/full-audit.py              # 全部 9 组（本地，含成品与渲染）
    python tools/full-audit.py --source-only  # 只跑源码层（CI 用：A–E、I）

九组检查：
  A README 实渲染      pandoc 渲染一遍，表识别成 <table>、列表成 <ol>/<ul>、段落里不能有裸竖线
  B README 本地链接     全部有效，0 死链
  C 目录 ↔ book 对位    32 行目录与 32 个文件一一对应，目录名与各节 H1 一致，节号连续
  D 条数 / 证据等级     576 条、六字段齐全、A518/B51/C7 与 README 声明一致
  E 交叉引用边界        「第 N 节第 M 条」的 N、M 都在有效范围内
  F 四件套成品          在线页 / 离线单文件 / PDF / EPUB / 封面 都在且体积正常
  G EPUB 结构          mimetype 置首且不压缩、XML 全合规、nav 条目数、toc.ncx、封面
  H 离线语料           __CORPUS__ 里 parts=32、docs=36（含 3 篇长文）
  I 仓库形态件         发布件 15 项 + tools/ 构建脚本

设计纪律（踩过坑才有的）：
  · 每个统计都必须打印「命中几个对象」。命中 0 一律报警——只认行尾的正则曾一条没匹配上却报「全部一致」。
  · 没有 pandoc 时 A 组降级为文本层检查，并明确打印「未做渲染验证」，不静默通过。
零依赖（除 A 组可选的 pandoc），只用标准库。
"""
import io, os, re, sys, glob, json, zipfile, subprocess, shutil, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARENT = os.path.dirname(ROOT)
def _local(name):
    """本机私有路径：同目录的 local_paths.py（不进仓库）。"""
    try:
        import local_paths
    except Exception:
        return None
    return getattr(local_paths, name, None)


# 和 build-pdf.py 同款：环境变量优先，其次本机私有配置，再次 PATH。
PANDOC = (os.environ.get('PANDOC') or _local('PANDOC')
          or shutil.which('pandoc') or 'pandoc')
EPUB = os.path.join(PARENT, '高性价比职场指南.epub')
OFFLINE = os.path.join(PARENT, '高性价比职场指南-全本.html')
PDF = os.path.join(PARENT, '高性价比职场指南.pdf')
SOURCE_ONLY = '--source-only' in sys.argv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
unq = __import__('urllib.parse', fromlist=['unquote']).unquote
fails = []


def sec(t):
    print('\n' + '=' * 62); print(t); print('=' * 62)


def need(cond, msg):
    if not cond:
        fails.append(msg)
    return cond


def load():
    return io.open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()


readme = load()
files = sorted(glob.glob(os.path.join(ROOT, 'book', '*.md')))

# ---------- A. README 渲染 ----------
sec('A. README 实渲染')
tmpl = None
try:
    probe = subprocess.run([PANDOC, '--version'], capture_output=True)
    has_pandoc = probe.returncode == 0
except Exception:
    has_pandoc = False
if has_pandoc:
    out = os.path.join(ROOT, '.audit-readme.html')
    subprocess.run([PANDOC, os.path.join(ROOT, 'README.md'), '-f', 'gfm', '-t', 'html',
                    '--wrap=none', '-o', out], capture_output=True)
    h = io.open(out, encoding='utf-8').read()
    os.remove(out)
    ntab, nol, nul, ndet = h.count('<table>'), h.count('<ol'), h.count('<ul'), h.count('<details')
    nbare = len(re.findall(r'<p>[^<]*\|[^<]*</p>', h))
    print('  table=%d  ol=%d  ul=%d  details=%d  段落裸竖线=%d' % (ntab, nol, nul, ndet, nbare))
    need(ntab == 7, 'table 数 %d ≠ 7' % ntab)
    need(nbare == 0, '有 %d 处段落内裸竖线（表没被识别）' % nbare)
    need(ndet == 1, 'details 数 %d ≠ 1' % ndet)
    for tag in ['table', 'ol', 'ul', 'details', 'tr', 'td', 'th']:
        o = len(re.findall(r'<%s[ >]' % tag, h)); c = h.count('</%s>' % tag)
        need(o == c, '<%s> 不配平 %d/%d' % (tag, o, c))
    if not fails:
        print('  ✓ 7 张表全部识别 / 无裸竖线 / 标签配平')
else:
    print('  ! 未找到 pandoc（%s），降级为文本层检查——未做渲染验证' % PANDOC)
    # 文本层：表格行必须连续（表头/分隔/数据行之间不能有空行）
    blocks = re.split(r'\n\s*\n', readme)
    broke = [b.split('\n')[0][:40] for b in blocks
             if b.lstrip().startswith('|') and '\n' in b and not re.match(r'^[|\s\-:]+$', b.split('\n')[1])]
    print('  疑似被空行截断的表格块: %d' % len(broke))
    need(len(broke) == 0, '有 %d 个表格块被空行截断' % len(broke))

# ---------- B. README 本地链接 ----------
sec('B. README 本地链接')
bad, ok, ext = [], 0, 0
for m in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', readme):
    txt, url = m.group(1), m.group(2)
    if url.startswith('http') or url.startswith('#'):
        ext += 1; continue
    p = unq(url.split('#')[0])
    if not p:
        continue
    if os.path.exists(os.path.normpath(os.path.join(ROOT, p))):
        ok += 1
    else:
        bad.append((txt, url))
print('  有效 %d / 失效 %d / 外链或锚点 %d（命中 %d 个链接）' % (ok, len(bad), ext, ok + len(bad) + ext))
for a, b in bad:
    print('    死链: %s -> %s' % (a, b[:70]))
need(len(bad) == 0, 'README 死链 %d' % len(bad))
need(ok + len(bad) >= len(files) + 3, '本地链接数 %d 偏少' % (ok + len(bad)))
if not bad:
    print('  ✓ 全部有效')

# ---------- C. 目录 ↔ book 对位 ----------
sec('C. README 目录 ↔ book/ 文件对位')
toc = re.findall(r'^(\d+)\.\s*\[([^\]]+)\]\((book/[^)]+)\)', readme, flags=re.M)
print('  目录行命中: %d   book/ 文件: %d' % (len(toc), len(files)))
need(len(toc) == len(files), '目录行 %d ≠ book 文件 %d' % (len(toc), len(files)))
need(len(toc) > 0, '目录行命中 0（正则失效）')
mis = []
for num, name, path in toc:
    full = os.path.normpath(os.path.join(ROOT, path))
    if not os.path.exists(full):
        mis.append('目录 %s → 文件不存在 %s' % (num, path)); continue
    t = io.open(full, encoding='utf-8').read()
    m = re.search(r'^#\s+(.+?)\s*$', t, flags=re.M)
    h1 = m.group(1) if m else ''
    if name not in h1:
        mis.append('第 %s 节 目录名「%s」≠ H1「%s」' % (num, name, h1))
for x in mis:
    print('  !! ' + x)
need(len(mis) == 0, '目录名/H1 不一致 %d' % len(mis))
nums = [int(n) for n, _, _ in toc]
need(nums == list(range(1, len(files) + 1)), '节号不连续')
if not mis and nums == list(range(1, len(files) + 1)):
    print('  ✓ 32 节一一对位、节号 1..32 连续')

# ---------- D. 条数 / 证据等级 ----------
sec('D. 条数与证据等级')
tot = 0; per = {}; grades = collections.Counter(); miss_field = []
for f in files:
    t = io.open(f, encoding='utf-8').read()
    n = len(re.findall(r'^###\s+', t, flags=re.M)); per[os.path.basename(f)] = n; tot += n
    for b in re.split(r'^### ', t, flags=re.M)[1:]:
        for k in ['成本', '说人话', '收益', '证据等级', '来源', '备注']:
            if not re.search(r'^- %s：' % k, b, flags=re.M):
                miss_field.append('%s 缺 %s' % (os.path.basename(f), k))
        g = re.search(r'^- 证据等级：(.)', b, flags=re.M)
        if g:
            grades[g.group(1)] += 1
print('  合计 %d 条 / %d 节，最大节 %s' % (tot, len(files), max(per.items(), key=lambda x: x[1])))
print('  证据等级现算: %s' % dict(grades))
need(tot == 576, '条数 %d ≠ 576' % tot)
need(len(miss_field) == 0, '六字段缺失 %d 处' % len(miss_field))
need(grades.get('A') == 518 and grades.get('B') == 51 and grades.get('C') == 7,
     '证据等级 %s ≠ A518/B51/C7' % dict(grades))
for num in ['576', '518', '51', '7']:
    need('%s 条' % num in readme, 'README 未声明 %s 条' % num)
if not miss_field:
    print('  ✓ 六字段齐全、等级与 README 声明一致')

# ---------- E. 交叉引用边界 ----------
sec('E. 交叉引用边界')
secs = {}
for f in files:
    m = re.match(r'(\d+)-', os.path.basename(f))
    t = io.open(f, encoding='utf-8').read()
    secs[int(m.group(1))] = len(re.findall(r'^###\s+', t, flags=re.M))
scan = files + sorted(glob.glob(os.path.join(ROOT, 'docs', '*.md')))
refs = []
for f in scan:
    t = io.open(f, encoding='utf-8').read()
    for m in re.finditer(r'第\s*(\d+)\s*节第\s*(\d+)\s*条', t):
        refs.append((os.path.basename(f), int(m.group(1)), int(m.group(2))))
print('  「第 N 节第 M 条」命中: %d 处' % len(refs))
need(len(refs) > 0, '交叉引用命中 0（正则失效）')
bad_ref = []
for f, s, k in refs:
    if s not in secs:
        bad_ref.append('%s: 第 %d 节不存在' % (f, s))
    elif k > secs[s]:
        bad_ref.append('%s: 第 %d 节第 %d 条越界（该节 %d 条）' % (f, s, k, secs[s]))
for x in bad_ref[:10]:
    print('    !! ' + x)
need(len(bad_ref) == 0, '交叉引用越界 %d 处' % len(bad_ref))
if not bad_ref:
    print('  ✓ 全部落在有效范围内')

if SOURCE_ONLY:
    sec('校验汇总（--source-only：已跳 F/G/H 成品组）')
    if fails:
        print('  ✗ 发现 %d 类问题:' % len(fails))
        for f in fails:
            print('    - ' + f)
        sys.exit(1)
    print('  ✓ 源码层 6 组检查全部通过')
    sys.exit(0)

# ---------- F. 四件套 ----------
sec('F. 四件套成品')
for name, p in [('在线检索页', os.path.join(ROOT, 'index.html')),
                ('离线单文件', OFFLINE), ('PDF', PDF), ('EPUB', EPUB),
                ('封面', os.path.join(ROOT, 'og.png'))]:
    e = os.path.exists(p); sz = os.path.getsize(p) if e else 0
    print('  %-10s %s  %9.1f KB' % (name, 'OK ' if e else '缺!', sz / 1024.0))
    need(e and sz > 20000, '%s 缺失或体积异常' % name)

# ---------- G. EPUB ----------
sec('G. EPUB 结构')
try:
    z = zipfile.ZipFile(EPUB)
    names = z.namelist()
    mi = z.getinfo('mimetype')
    need(names[0] == 'mimetype' and mi.compress_type == 0, 'mimetype 未置首或未 STORED')
    pages = [n for n in names if n.endswith('.xhtml')]
    import xml.dom.minidom as M
    xb = []
    for n in names:
        if n.endswith(('.xhtml', '.opf', '.ncx', '.xml')):
            try:
                M.parseString(z.read(n))
            except Exception:
                xb.append(n)
    print('  mimetype 置首+STORED=%s | XHTML %d 页 | XML 不合规 %s' % (
        names[0] == 'mimetype' and mi.compress_type == 0, len(pages), xb or '无'))
    need(not xb, 'EPUB XML 不合规 %d' % len(xb))
    need(len(pages) == 40, 'EPUB 页数 %d ≠ 40' % len(pages))
    nav = z.read([n for n in names if n.endswith('nav.xhtml')][0]).decode('utf-8')
    need(nav.count('<li>') > 600, 'nav 条目过少 %d' % nav.count('<li>'))
    need(any(n.endswith('.ncx') for n in names), '缺 toc.ncx')
    need(any(n.endswith('cover.png') for n in names), '缺封面图')
    print('  nav 条目 %d' % nav.count('<li>'))
except Exception as e:
    need(False, 'EPUB 打开失败 %s' % e)

# ---------- H. 离线语料 ----------
sec('H. 离线单文件语料')
try:
    off = io.open(OFFLINE, encoding='utf-8').read()
    m = re.search(r'window\.__CORPUS__\s*=\s*', off)
    need(bool(m), '缺 __CORPUS__')
    obj, _ = json.JSONDecoder().raw_decode(off[m.end():])
    parts, docs = obj.get('parts', {}), obj.get('docs', {})
    print('  parts(节)=%d  docs=%d' % (len(parts), len(docs)))
    need(len(parts) == 32, 'parts %d ≠ 32' % len(parts))
    need(len(docs) == 36, 'docs %d ≠ 36' % len(docs))
    longx = [k for k in docs if re.match(r'docs/[^/]+\.md$', k)]
    need(len(longx) == 3, '长文 %d ≠ 3' % len(longx))
    print('  长文 %d 篇: %s' % (len(longx), [x.split('/')[-1] for x in longx]))
except Exception as e:
    need(False, '离线语料解析失败 %s' % e)

# ---------- I. 仓库形态件 ----------
sec('I. 仓库形态件')
missing = []
for rel in ['README.md', 'CLAUDE.md', 'AGENTS.md', 'LICENSE', 'LICENSE-CODE', '.nojekyll',
            'robots.txt', '.gitignore', 'og.png', 'index.html',
            'skills/workplace-decision-guide/SKILL.md',
            '.claude/skills/workplace-decision-guide/SKILL.md',
            '.github/FUNDING.yml',
            '.github/workflows/check.yml', '.github/workflows/book.yml',
            '.github/workflows/links.yml']:
    if not os.path.exists(os.path.join(ROOT, rel)):
        missing.append(rel)
for x in missing:
    print('  缺: %s' % x)
need(len(missing) == 0, '仓库件缺失 %d：%s' % (len(missing), missing))
tools = sorted(os.path.basename(x) for x in glob.glob(os.path.join(ROOT, 'tools', '*')))
if not missing:
    print('  ✓ 16 项发布件就位')
print('  tools/: %s' % tools)
need(any(t.startswith('build-') for t in tools), 'tools/ 里没有构建脚本')

# ---------- 汇总 ----------
sec('校验汇总')
if fails:
    print('  ✗ 发现 %d 类问题:' % len(fails))
    for f in fails:
        print('    - ' + f)
    sys.exit(1)
print('  ✓ 全部通过（9 组检查）')
