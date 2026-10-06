# -*- coding: utf-8 -*-
"""从指定 URL 里抽出若干个「第 X 条」的原文（含之一/之二这类带后缀的条）。

用法:
    python tools/fetch-clause.py <url> 二百五十三条之一 二百六十六条 ...
"""
import re
import sys
import urllib.request
import gzip

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 下一条的起头：第 + 数字/汉字数字 + 条，可带「之一」
NEXT_RE = re.compile(r"第\s?[0-9一二三四五六七八九十百零]{1,6}\s?条(?:之[一二三四五六七八九十]{1,2})?(?!条|之)")


def fetch_text(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    for enc in ("utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", "ignore")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    return re.sub(r"\s+", " ", text)


def clauses(text, num):
    """num 传裸条号，如 '二百五十三条之一'。"""
    out = []
    # 正则必须把「条」字写进模式里，尾巴只排除「条」「之」两种续写。
    # 不能写成 第三(?![\u4e00-\u9fa5])——「条」本身就在 \u4e00-\u9fa5 里，
    # 那样写会把所有正常条文一起排除掉，永远命中 0 处。
    head = re.compile(r"第\s?" + re.escape(num) + r"条(?!条|之)")
    for m in head.finditer(text):
        n = NEXT_RE.search(text, m.end())
        end = n.start() if n else min(len(text), m.start() + 1000)
        chunk = text[m.start():end].strip()
        if len(chunk) > 20:
            out.append(chunk)
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    url, nums = sys.argv[1], sys.argv[2:]
    text = fetch_text(url)
    print(f"# {url}\n# 全文 {len(text):,} 字符\n")
    for num in nums:
        got = clauses(text, num)
        print(f"=== 第 {num} 条（命中 {len(got)} 处）===")
        for c in got[:2]:
            print("  " + c[:1000])
        if not got:
            print("  !! 未找到")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
