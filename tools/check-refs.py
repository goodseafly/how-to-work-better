# -*- coding: utf-8 -*-
"""引用锚点检查器。

本书规定：正文里引用其他条目时，必须写成
    见本节第 3 条（举证责任在公司）        # 同节
    见第 4 节第 3 条（举证责任在公司）      # 跨节到条目
    见第 12 节（被针对和被逼走）            # 跨节到节
括号里的锚点词，必须和目标标题有连续三个汉字相同。

检查三件事：
  1. 目标是否存在（节号、条号）
  2. 括号锚点词和目标标题是否有连续 3 个汉字重合
  3. 条号后面有没有漏掉括号

用法:
    python tools/check-refs.py
"""
import os, re, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, 'book')

# 找「第 N 节第 M 条（锚点）」「本节第 M 条（锚点）」「第 N 节（锚点）」
SEC_ITEM = re.compile(r'第\s?(\d+)\s?节\s?第\s?(\d+)\s?条\s?[（(]([^）)]{1,30})[）)]')
THIS_ITEM = re.compile(r'本节\s?第\s?(\d+)\s?条\s?[（(]([^）)]{1,30})[）)]')
SEC_ONLY = re.compile(r'第\s?(\d+)\s?节\s?[（(]([^）)]{1,30})[）)]')
# 条号后面直接跟标点或者没有括号的，报出来人工看
LOOSE = re.compile(r'第\s?\d+\s?条(?![（(])')
# 节首分组导览写成「短名（第 N 条）」，条号后面是右括号，会被 LOOSE 误报。
# 导览整段不参与引用检查。
GUIDE_MARK = '本节条目按主题分成'


def cjk_runs(a, b, n=3):
    """a 和 b 是否存在长度 >= n 的公共汉字子串。返回最长公共长度。"""
    if not a or not b:
        return 0
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            best = max(best, k)
    return best


def main():
    # 收集每节标题：sec_no -> {item_no: title}
    secs = {}          # int -> {'file':.., 'items': {int: title}}
    readme = os.path.join(ROOT, 'README.md')
    rt = open(readme, encoding='utf-8').read()
    for m in re.finditer(r'^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*$', rt, re.M):
        secs.setdefault(int(m.group(1)), {'file': None, 'items': {}, 'q': m.group(2)})
    # 「只指到节」的锚点词，比的是目录里的**节名**，不是「想回答的问题」那一栏。
    # 目录里两种写法，必须分开匹配，不能用一个贪婪的 (.+) 兜底：
    #   已完稿：  1. [节名](book/01-xxx.md)：描述……
    #   待撰写：  5. 节名（待撰写）
    # 兜底写法会把「：描述」整段吞进节名，让锚点检查假通过。
    for m in re.finditer(r'^(\d+)\.\s*\[([^\]]+)\]\([^)]*\)', rt, re.M):
        secs.setdefault(int(m.group(1)), {'file': None, 'items': {}, 'q': ''})
        secs[int(m.group(1))]['name'] = m.group(2).strip()
    for m in re.finditer(r'^(\d+)\.\s*([^\[\n]+?)（待撰写）', rt, re.M):
        secs.setdefault(int(m.group(1)), {'file': None, 'items': {}, 'q': ''})
        secs[int(m.group(1))]['name'] = m.group(2).strip()

    for path in sorted(glob.glob(os.path.join(BOOK, '*.md'))):
        name = os.path.basename(path)
        mm = re.match(r'(\d+)-', name)
        if not mm:
            continue
        sno = int(mm.group(1))
        text = open(path, encoding='utf-8').read()
        items = {}
        for h in re.finditer(r'^###\s*(\d+)\.\s*(.+?)\s*$', text, re.M):
            items[int(h.group(1))] = h.group(2)
        secs.setdefault(sno, {'file': name, 'items': {}, 'q': ''})
        secs[sno]['file'] = name
        secs[sno]['items'] = items

    problems, checked = [], 0
    # 只扫读者向文件：book/ 正文 + docs/ 顶层长文。
    # docs/核实记录/ 是内部笔记，用「第 N 条」当索引而非锚点引用，不适用本条体例。
    scan = sorted(glob.glob(os.path.join(BOOK, '*.md'))) + sorted(glob.glob(os.path.join(ROOT, 'docs', '*.md')))
    for path in scan:
        name = os.path.basename(path)
        mm = re.match(r'(\d+)-', name)
        cur = int(mm.group(1)) if mm else 0
        text = open(path, encoding='utf-8').read()
        lines = text.split('\n')
        gmask, in_g = [], False
        for _l in lines:
            if _l.startswith(GUIDE_MARK):
                in_g = True
            elif _l.startswith('### '):
                in_g = False
            gmask.append(in_g)

        for ln, line in enumerate(lines, 1):
            if gmask[ln - 1]:
                continue
            for m in SEC_ITEM.finditer(line):
                checked += 1
                s, i, anch = int(m.group(1)), int(m.group(2)), m.group(3)
                if s not in secs or i not in secs[s]['items']:
                    problems.append('%s:%d 指路失效 -> 第 %d 节第 %d 条 不存在' % (name, ln, s, i))
                    continue
                title = secs[s]['items'][i]
                k = cjk_runs(anch, title)
                if k < 3:
                    problems.append('%s:%d 锚点不匹配 -> 「%s」vs 第 %d 节第 %d 条标题「%s」(重合 %d 字)'
                                    % (name, ln, anch, s, i, title, k))

            for m in THIS_ITEM.finditer(line):
                checked += 1
                i, anch = int(m.group(1)), m.group(2)
                if i not in secs[cur]['items']:
                    problems.append('%s:%d 指路失效 -> 本节第 %d 条 不存在' % (name, ln, i))
                    continue
                title = secs[cur]['items'][i]
                k = cjk_runs(anch, title)
                if k < 3:
                    problems.append('%s:%d 锚点不匹配 -> 「%s」vs 本节第 %d 条标题「%s」(重合 %d 字)'
                                    % (name, ln, anch, i, title, k))

            for m in SEC_ONLY.finditer(line):
                s, anch = int(m.group(1)), m.group(2)
                if re.search(r'该节|已引|见上|此处|原文', anch):
                    continue  # 核实记录里的括号是叙述，不是锚点
                if s not in secs:
                    problems.append('%s:%d 指路失效 -> 第 %d 节 不存在' % (name, ln, s))
                    continue
                q = secs[s].get('name') or secs[s].get('q')
                if q:
                    checked += 1
                    k = cjk_runs(anch, q)
                    if k < 3:
                        problems.append('%s:%d 节锚点不匹配 -> 「%s」vs 第 %d 节节名「%s」(重合 %d 字)'
                                        % (name, ln, anch, s, q, k))

            # 裸条号：条号后没有括号的引用
            for m in LOOSE.finditer(line):
                seg = line[max(0, m.start() - 6):m.end()]
                if '节' not in seg:
                    problems.append('%s:%d 裸条号 -> %r' % (name, ln, seg))

    print('=== 引用锚点检查 ===')
    print('已检查带锚点引用 %d 处' % checked)
    print('问题 %d 处' % len(problems))
    for p in problems:
        print('  -', p)
    return len(problems)


if __name__ == '__main__':
    n = main()
    print('\n结论：%s' % ('通过' if n == 0 else '有 %d 处待修' % n))
