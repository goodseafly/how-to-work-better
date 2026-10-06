# -*- coding: utf-8 -*-
"""本书正文检查器：格式审计 + 全部引用链接可用性核验。

用法:
    python tools/check-body.py            # 只做格式审计
    python tools/check-body.py --urls     # 追加链接核验（联网）
"""
import os, re, sys, io, glob, json, ssl, time, threading
import urllib.request, urllib.error, concurrent.futures
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, 'book')
README = os.path.join(ROOT, 'README.md')

REQ = ['成本：', '说人话：', '收益：', '证据等级：', '来源：', '备注：']
TAG_RE = re.compile(r'<!-- 成本标签: 钱=(0|少|多) 时间=(少|中|多) 毅力=(否|些|是) 收益=(大|中|小) 口径=(金钱|时间|健康|岗位|自由) -->')
H_RE = re.compile(r'^### (\d+)\. (.+)$')
REF_RE = re.compile(r'第\s?(\d+)\s?条')
URL_RE = re.compile(r'https?://(?:[^\s>）)、；()]|\([^\s>）)、；]*\))+')
# 节首分组导览（CLAUDE.md 规定写成「短名（第 N 条）」）里的条号是目录式列举，
# 条号后面跟的是右括号，会撞上「第 N 条 前 4 字内必须有节」这条裸条号规则。
# 导览不是正文引用，审计前整段摘掉。
GUIDE_MARK = '本节条目按主题分成'


def strip_guide(text):
    out, in_guide = [], False
    for line in text.split('\n'):
        if line.startswith(GUIDE_MARK):
            in_guide = True
            continue
        if line.startswith('### '):
            in_guide = False
        if not in_guide:
            out.append(line)
    return '\n'.join(out)


def audit():
    total, problems = 0, []
    per_section, ev_count, tag_count = {}, {}, {}
    maxsec = 0
    paths = sorted(glob.glob(os.path.join(BOOK, '*.md')))
    for path in paths:
        name = os.path.basename(path)
        lines = open(path, encoding='utf-8').read().split('\n')
        if not lines[0].startswith('[← 回总目录]'):
            problems.append('%s 缺首页返回链接' % name)
        heads = [l for l in lines if H_RE.match(l)]
        nums = [int(H_RE.match(h).group(1)) for h in heads]
        per_section[name] = len(heads)
        total += len(heads)
        if nums != list(range(1, len(nums) + 1)):
            problems.append('%s 条号不连续: %s' % (name, nums))
        for i, h in enumerate(heads):
            idx = lines.index(h)
            end = lines.index(heads[i + 1]) if i + 1 < len(heads) else len(lines)
            block = lines[idx:end]
            no = H_RE.match(h).group(1)
            tags = [l for l in block if '成本标签' in l]
            if len(tags) != 1:
                problems.append('%s 第%s条 成本标签行数=%d' % (name, no, len(tags)))
            elif not TAG_RE.match(tags[0].strip()):
                problems.append('%s 第%s条 标签格式错: %s' % (name, no, tags[0][:70]))
            else:
                m = TAG_RE.match(tags[0].strip())
                for k, v in zip(['钱', '时间', '毅力', '收益', '口径'], m.groups()):
                    tag_count[k] = tag_count.get(k, {})
                    tag_count[k][v] = tag_count[k].get(v, 0) + 1
            for r in REQ:
                n = sum(1 for l in block if l.startswith('- ' + r))
                if n != 1:
                    problems.append('%s 第%s条 字段「%s」出现 %d 次' % (name, no, r, n))
            bt = [l for l in block if l.startswith('- 备注：')]
            if bt:
                urls = URL_RE.findall(bt[0])
                if len(urls) > 1:
                    problems.append('%s 第%s条 备注有 %d 个链接' % (name, no, len(urls)))
                if len(bt[0]) > 900:
                    problems.append('%s 第%s条 备注 %d 字' % (name, no, len(bt[0])))
            # 阈值按 CLAUDE.md 的「120 字以内」定。这里曾经写成 130，
            # 结果 121~130 那一段成了盲区，全库攒了 9 条超标的才被发现。
            sr = [l for l in block if l.startswith('- 说人话：')]
            if sr and len(sr[0][len('- 说人话：'):]) > 120:
                problems.append('%s 第%s条 说人话 %d 字（上限 120）' % (name, no, len(sr[0])))
            ev = [l for l in block if l.startswith('- 证据等级：')]
            if ev:
                v = ev[0].strip()[-1]
                if v not in 'ABC':
                    problems.append('%s 第%s条 证据等级异常: %s' % (name, no, ev[0][:40]))
                else:
                    ev_count[v] = ev_count.get(v, 0) + 1
            src = [l for l in block if l.startswith('- 来源：')]
            if src and 'http' not in src[0] and '无直接法条' not in src[0]:
                problems.append('%s 第%s条 来源无链接' % (name, no))
        maxsec = max(maxsec, len(heads))

    alltext = ''.join(strip_guide(open(p, encoding='utf-8').read()) + '\n' for p in paths)
    bare = [alltext[max(0, m.start() - 4):m.end()] for m in REF_RE.finditer(alltext)
            if '节' not in alltext[max(0, m.start() - 4):m.end()]]

    print('=== 每节条数 ===')
    for k, v in per_section.items():
        print('  %-42s %d' % (k, v))
    print('  合计 %d 条，最大节 %d 条' % (total, maxsec))
    print('=== 证据等级 === %s' % ev_count)
    for k, v in tag_count.items():
        print('=== 成本标签·%s === %s' % (k, v))
    print('=== 格式问题 %d 处 ===' % len(problems))
    for p in problems:
        print('  -', p)
    print('=== 裸条号引用 %d 处 ===' % len(bare))
    for b in bare:
        print('  -', repr(b))
    return total, len(problems) + len(bare)


def check_urls():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # 有些站点（例如 gongbao.court.gov.cn）先下发 cookie 再重定向到同一地址，
    # 不带 cookie 的请求会一直陷在同址跳转里，被误判成死链。加一个会话级 cookie 罐。
    import http.cookiejar
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        urllib.request.HTTPSHandler(context=ctx))
    urls = set()
    for path in sorted(glob.glob(os.path.join(BOOK, '*.md'))):
        urls |= set(URL_RE.findall(open(path, encoding='utf-8').read()))
    urls = sorted(urls)

    # PubMed 对脚本请求返回 203 加一张机器人校验页，直抓会把它误判成死链。
    # 这类链接改用 E-utilities 接口按 PMID 核验，接口认了就算通过。
    PUBMED_RE = re.compile(r'^https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?$')
    EUTILS = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
              'esummary.fcgi?db=pubmed&id=%s&retmode=json')
    UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # E-utilities 无限流密钥时限 3 次/秒，检查器开 8 个线程一起打必然撞 429。
    # 用锁串行化并留间隔，429 再退避重试；连续撞限流就归 MANUAL 交人工看，
    # 不能把限流当成链接失效。
    _pm_lock = threading.Lock()

    def chk_pubmed(pmid):
        for attempt in range(4):
            try:
                with _pm_lock:
                    time.sleep(0.5)
                    req = urllib.request.Request(EUTILS % pmid, headers=UA)
                    raw = opener.open(req, timeout=25).read().decode('utf-8', 'replace')
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 3:
                    with _pm_lock:
                        time.sleep(2.0 * (attempt + 1))
                    continue
                return 'MANUAL', 'E-utilities 未通过（%s），需人工打开' % e
            except Exception as e:
                return 'ERR', str(e)[:50]
            try:
                rec = (json.loads(raw).get('result') or {}).get(pmid)
            except Exception as e:
                return 'ERR', 'E-utilities 返回无法解析：%s' % str(e)[:30]
            if not rec or rec.get('error'):
                return 'BAD', 'E-utilities 查无此 PMID'
            # 统一返回 200，结果统计循环只认 200。
            return 200, '%s | %s' % (rec.get('pubdate', ''), (rec.get('title') or '')[:70])
        return 'MANUAL', 'E-utilities 连续撞限流，需人工打开'

    def chk(u):
        m = PUBMED_RE.match(u)
        if m:
            return (u,) + chk_pubmed(m.group(1))
        req = urllib.request.Request(u, headers=UA)
        try:
            r = opener.open(req, timeout=25)
            # 203/429 是站点在挡机器人，不代表链接失效，单独归一类交人工看。
            if r.status in (203, 429):
                return u, 'MANUAL', '站点挡机器人（%s）' % r.status
            return u, r.status, len(r.read())
        except Exception as e:
            return u, 'ERR', str(e)[:50]

    print('\n=== 链接核验（%d 个） ===' % len(urls))
    bad, manual = 0, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for u, st, info in ex.map(chk, urls):
            if st == 200:
                print('  OK   %-6s %s' % (st, u))
            elif st == 'MANUAL':
                manual.append(u)
                print('  ??   %-6s %s  <- %s' % (st, u, info))
            else:
                bad += 1
                print('  XX   %-6s %s  <- %s' % (st, u, info))
    if manual:
        print('  机器校验受阻 %d 个（平台在挡机器人，不计入失效，但需人工打开过一遍）：' % len(manual))
        for u in manual:
            print('       %s' % u)
    print('  失效 %d 个' % bad)
    return bad


if __name__ == '__main__':
    n, bad = audit()
    if '--urls' in sys.argv:
        bad += check_urls()
    print('\n结论：%s' % ('通过' if bad == 0 else '有 %d 项待处理' % bad))
