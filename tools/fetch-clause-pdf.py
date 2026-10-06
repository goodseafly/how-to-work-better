# -*- coding: utf-8 -*-
"""从法律法规 PDF 里抽出指定条文的原文，用于「把正文说法和原文逐字对」。

用法:
    python _clausepdf.py <pdf-url-or-path> <裸条号> [更多裸条号 ...]

为什么要用 PDF：人社部、国家法律法规数据库（含 wb.flk.npc.gov.cn）的 HTML 详情页
对脚本请求会返回反爬壳或前端应用外壳，正文取不到；但同一站点的 PDF 直链可以正常下载。
"""
import io
import re
import ssl
import sys
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# npc.gov.cn 及其 wb 子域名的证书链在脚本环境里握手失败，
# 但页面本身可访问；跳过校验只影响本地脚本取文本，不影响正文引用的 URL。
_NO_VERIFY = ssl.create_default_context()
_NO_VERIFY.check_hostname = False
_NO_VERIFY.verify_mode = ssl.CERT_NONE

# 下一条的起头：第 + 数字/汉字数字 + 条，可带「之一」
NEXT_RE = re.compile(r"第[0-9一二三四五六七八九十百零]{1,6}条(?:之[一二三四五六七八九十]{1,2})?")


def load(src):
    if src.lower().startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={
            "User-Agent": UA,
            "Accept": "application/pdf,*/*",
        })
        with urllib.request.urlopen(req, timeout=90, context=_NO_VERIFY) as r:
            data = r.read()
        print(f"# 下载 {len(data):,} 字节")
        stream = io.BytesIO(data)
    else:
        with open(src, "rb") as f:
            stream = io.BytesIO(f.read())

    from pypdf import PdfReader
    reader = PdfReader(stream)
    text = " ".join((p.extract_text() or "") for p in reader.pages)
    # PDF 抽出来的文本里常有空格和换行，全部去掉再匹配
    return re.sub(r"\s+", "", text), len(reader.pages)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    text, pages = load(sys.argv[1])
    print(f"# 页数 {pages}，去空白后 {len(text):,} 字符\n")
    for num in sys.argv[2:]:
        # 不能用 (?![\u4e00-\u9fa5]) 当边界：PDF 文本剥掉空白后，
        # 「第五条」后面直接就是正文汉字，先行断言必然失败。
        # 只需要排除「第五条之一」这种带后缀的情形即可。
        # 也不会误配更长的条号：找「第五条」时，「第十五条」的「五」前面是「十」不是「第」。
        head = re.compile(r"第" + re.escape(num.lstrip("第").rstrip("条")) + r"条(?![条之])")
        got = []
        for m in head.finditer(text):
            n = NEXT_RE.search(text, m.end())
            end = n.start() if n else min(len(text), m.start() + 900)
            chunk = text[m.start():end]
            if len(chunk) > 15:
                got.append(chunk)
        print(f"=== 第 {num} 条（命中 {len(got)} 处）===")
        if not got:
            print("  !! 未找到\n")
            continue
        for c in got[:2]:
            print("  " + c[:900])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
