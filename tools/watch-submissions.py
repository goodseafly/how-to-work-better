# -*- coding: utf-8 -*-
"""
每周监视三处投稿通道：有没有回复、有没有被收录。

三处：
  1. HelloGitHub 月刊  521xueweihan/HelloGitHub#3878
  2. GitHubDaily       GitHubDaily/GitHubDaily#1160
  3. 阮一峰周刊         ruanyf/weekly#12127

判定口径：
  - 「有回复」  = issue 评论数增加（或已有评论的内容变化）
  - 「被收录」  = 对应仓库里出现除自己投稿外的、提及 goodseafly/how-to-make-work-pay
                  的 issue（月刊/周刊正文即 issue 正文）
  - 「被拒/关闭」= issue state 由 open 变 closed

快照：F:/高性价比人生指南/.workbuddy/submit-watch.json
用法：
  python tools/watch-submissions.py            # 对比上次快照，输出变化
  python tools/watch-submissions.py --baseline # 只建立基线，不报变化
"""
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
TOKEN_PATH = r'D:/Users/92861/.ghtoken'
SNAPSHOT = r'F:/高性价比人生指南/.workbuddy/submit-watch.json'
BOOK = 'goodseafly/how-to-make-work-pay'

TARGETS = [
    dict(key='hellogithub', name='HelloGitHub 月刊',
         repo='521xueweihan/HelloGitHub', number=3878,
         note='入选会出现在月刊 issue 正文'),
    dict(key='githubdaily', name='GitHubDaily',
         repo='GitHubDaily/GitHubDaily', number=1160,
         note='收录后通常有回复或转载推文'),
    dict(key='ruanyf', name='阮一峰周刊',
         repo='ruanyf/weekly', number=12127,
         note='入选会出现在周刊 issue 正文'),
]


def now_cst():
    return datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')


def token():
    with io.open(TOKEN_PATH, encoding='utf-8') as f:
        return f.read().strip()


def api(url, tok):
    req = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + tok,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'seafly-submit-watch',
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def load_snapshot():
    if os.path.exists(SNAPSHOT):
        try:
            with io.open(SNAPSHOT, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def fetch_one(t, tok):
    """返回单条投稿的当前状态；查询失败返回 dict(error=...)"""
    out = dict(key=t['key'], name=t['name'], url='https://github.com/%s/issues/%d' % (t['repo'], t['number']))
    try:
        d = api('https://api.github.com/repos/%s/issues/%d' % (t['repo'], t['number']), tok)
    except urllib.error.HTTPError as e:
        out['error'] = 'HTTP %s' % e.code
        return out
    except Exception as e:
        out['error'] = repr(e)[:120]
        return out
    out['state'] = d['state']
    out['comments'] = d['comments']
    out['labels'] = [l['name'] for l in d.get('labels', [])]
    out['updated_at'] = d['updated_at']
    out['closed_at'] = d.get('closed_at')
    out['title'] = d['title']
    cl = []
    if d['comments']:
        try:
            cs = api('https://api.github.com/repos/%s/issues/%d/comments?per_page=100' % (t['repo'], t['number']), tok)
            for c in cs:
                cl.append(dict(id=c['id'], user=c['user']['login'], at=c['created_at'],
                               body=(c['body'] or '')[:400]))
        except Exception as e:
            out['comment_error'] = repr(e)[:100]
    out['comment_list'] = cl
    return out


def fetch_mentions(t, tok):
    """在投稿目标仓库里搜本书的被提及情况，排除自己提交的那条"""
    q = urllib.parse.quote('"how-to-make-work-pay" OR "how-to-work-better" repo:%s in:title,body,comments' % t['repo'])
    try:
        d = api('https://api.github.com/search/issues?q=%s&per_page=40' % q, tok)
    except Exception as e:
        return dict(error=repr(e)[:120])
    hits = []
    for it in d.get('items', []):
        is_self = ('/issues/%d' % t['number']) in it['html_url']
        hits.append(dict(number=it['number'], title=it['title'], url=it['html_url'],
                         state=it['state'], self=is_self,
                         created=it['created_at']))
    return dict(total=d.get('total_count'), hits=hits)


def main():
    baseline_only = '--baseline' in sys.argv
    tok = token()
    prev = load_snapshot()

    cur = dict(checked_at=now_cst(), issues={}, mentions={}, book=None)
    errors = []

    for t in TARGETS:
        one = fetch_one(t, tok)
        cur['issues'][t['key']] = one
        if 'error' in one:
            errors.append('%s: %s' % (one['name'], one['error']))
        m = fetch_mentions(t, tok)
        cur['mentions'][t['key']] = m
        if 'error' in m:
            errors.append('%s 检索: %s' % (one['name'], m['error']))

    try:
        b = api('https://api.github.com/repos/%s' % BOOK, tok)
        cur['book'] = dict(stars=b['stargazers_count'], forks=b['forks_count'],
                           watchers=b['subscribers_count'], open_issues=b['open_issues_count'])
    except Exception as e:
        errors.append('书仓库指标: %r' % e)

    # ---------- 报告 ----------
    L = []
    L.append('# 投稿监视 · %s' % cur['checked_at'])
    L.append('')

    changes = []
    for t in TARGETS:
        one = cur['issues'][t['key']]
        if 'error' in one:
            L.append('## %s — 查询失败（%s）' % (t['name'], one['error']))
            L.append('')
            continue
        p = (prev or {}).get('issues', {}).get(t['key']) if prev else None
        tag = []
        if one['state'] != 'open':
            tag.append('**已关闭**')
        if one['comments']:
            tag.append('**有 %d 条回复**' % one['comments'])
        L.append('## %s%s' % (t['name'], ('  ·  ' + '  '.join(tag)) if tag else '  ·  暂无回复'))
        L.append('- 链接 %s' % one['url'])
        L.append('- 状态 %s｜评论 %d｜标签 %s｜更新 %s' % (
            one['state'], one['comments'],
            ('、'.join(one['labels']) if one['labels'] else '无'),
            one['updated_at']))
        if p and 'state' in p:
            if p['state'] != one['state']:
                changes.append('%s 状态 %s → %s' % (t['name'], p['state'], one['state']))
            if p.get('labels', []) != one['labels']:
                changes.append('%s 标签 %s → %s' % (t['name'], p.get('labels'), one['labels']))
            known = {c['id'] for c in p.get('comment_list', [])}
            newc = [c for c in one['comment_list'] if c['id'] not in known]
            if newc:
                changes.append('%s 新增 %d 条回复' % (t['name'], len(newc)))
            else:
                newc = []
        else:
            newc = one['comment_list']
        for c in newc:
            L.append('  - 新回复 @%s（%s）：%s' % (c['user'], c['at'], c['body'].replace('\n', ' ')))
        # 收录
        m = cur['mentions'][t['key']]
        if 'error' in m:
            L.append('- 收录检索失败：%s' % m['error'])
        else:
            others = [h for h in m['hits'] if not h['self']]
            if others:
                L.append('- **检出收录/提及 %d 处**' % len(others))
                for h in others[:6]:
                    L.append('  - #%s %s（%s）%s' % (h['number'], h['title'][:60], h['state'], h['url']))
            else:
                L.append('- 收录：尚无（本仓库内未出现除投稿外的提及）')
            pm = (prev or {}).get('mentions', {}).get(t['key'], {}) if prev else {}
            if pm and 'hits' in pm:
                pknown = {h['number'] for h in pm['hits']}
                for h in others:
                    if h['number'] not in pknown:
                        changes.append('%s 新增收录处 #%s %s' % (t['name'], h['number'], h['title'][:40]))
        L.append('')

    if cur.get('book'):
        b = cur['book']
        L.append('## 书仓库指标（参考）')
        L.append('- Star %d｜Fork %d｜Watch %d｜Open issues %d' % (
            b['stars'], b['forks'], b['watchers'], b['open_issues']))
        pb = (prev or {}).get('book') if prev else None
        if pb:
            ds = b['stars'] - pb.get('stars', 0)
            L.append('- 较上次：Star %s%d' % ('+' if ds >= 0 else '', ds))
        L.append('')

    L.append('## 结论')
    if errors:
        L.append('- 有 %d 项查询失败：%s' % (len(errors), '；'.join(errors)))
    if not prev:
        L.append('- 首次运行，已建立基线。')
    elif changes:
        L.append('- **检出 %d 项变化**：' % len(changes))
        for c in changes:
            L.append('  - %s' % c)
    else:
        L.append('- 三条投稿均无新回复、无收录、状态未变。')

    report = '\n'.join(L)

    # ---------- 落盘 ----------
    if errors and prev:
        # 有查询失败时不覆盖快照，避免下次误报
        sys.stderr.write('注意：存在查询失败，本次不更新快照\n')
    else:
        d = os.path.dirname(SNAPSHOT)
        if not os.path.isdir(d):
            os.makedirs(d)
        tmp = SNAPSHOT + '.tmp'
        with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(cur, ensure_ascii=False, indent=1))
        os.replace(tmp, SNAPSHOT)

    print(report)
    print('\nCHANGES: %d' % (0 if (baseline_only or not prev) else len(changes)))
    print('ERRORS: %d' % len(errors))
    return 0


if __name__ == '__main__':
    sys.exit(main())
