$--
$-- pandoc 的 typst 模板（只认 $body$ 和几个 -V 变量），不用 pandoc 自带的 conf()：
$-- 自带模板把页面设置锁在 conf() 里，改不了页眉页脚，所以这里自己排。
$-- 开头到 divider 那段是 pandoc 生成的正文要用的辅助定义，照抄自 `pandoc -D typst`，别删。
$--
#set terms(hanging-indent: 1.5em)

#set table(inset: 6pt, stroke: none)
// pandoc 把表格塞进 align(center) 里，单元格会跟着居中，中文表格左对齐才好读
#show table.cell: it => align(left, it)

#let horizontalRule = line(start: (25%, 0%), end: (75%, 0%))
#let divider = if "divider" in std { divider } else { horizontalRule }

#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: image): set figure.caption(position: bottom)
// 长表格要能跨页，否则整块挤不下就留一页白
#show figure: set block(breakable: true)
#set smartquote(enabled: false)

// ---------- 版面 ----------
#set document(title: "$booktitle$", author: "eternity4719")
#set text(
  // 西文用 typst 自带的 Libertinus，中文按可用性往后找：CI 上是 Noto，本机是雅黑
  font: ("Libertinus Serif", "Noto Serif CJK SC", "Noto Serif SC", "Source Han Serif SC", "Noto Sans CJK SC", "Microsoft YaHei", "SimSun"),
  size: 10.5pt, lang: "zh", region: "cn",
)
#set par(justify: false, leading: 0.78em, spacing: 0.9em)
#set list(indent: 0.6em, spacing: 0.75em)
#show raw: set text(font: ("DejaVu Sans Mono", "Noto Sans Mono CJK SC", "Consolas"), size: 9pt)
#show link: set text(fill: rgb("#1a4fb4"))
#show heading: set block(sticky: true, above: 1.5em, below: 0.65em)
#show heading.where(level: 1): set text(19pt)
#show heading.where(level: 2): set text(14pt)
#show heading.where(level: 3): set text(11.5pt)
// 每节另起一页；weak 保证前一页正好排满时不多出一张空页
#show heading.where(level: 1): it => { pagebreak(weak: true); it }

// 页眉：左边书名，右边当前节名；一节的头一页不打页眉
#let running-head = context {
  let next = query(selector(heading.where(level: 1)).after(here())).at(0, default: none)
  if next != none and next.location().page() == here().page() { return }
  let seen = query(selector(heading.where(level: 1)).before(here()))
  if seen.len() == 0 { return }
  set text(8.5pt, fill: luma(120))
  grid(columns: (1fr, auto), align(left)[$booktitle$], align(right)[#seen.last().body])
  v(-7pt)
  line(length: 100%, stroke: 0.4pt + luma(215))
}

// ---------- 封面 ----------
#set page(paper: "a4", margin: (x: 2.2cm, top: 2.2cm, bottom: 2cm), header: none, footer: none)
#align(center + horizon)[
  #image("/og.png", width: 100%)
  #v(1.2cm)
  #block(width: 80%)[#text(11.5pt, fill: luma(60))[$subtitle$]]
  #v(2cm)
  #text(10pt, fill: luma(90))[
    生成于 $builddate$（北京时间）　·　正文提交 $commit$ \
    正文每天都在改，以在线版为准：$site$ \
    在线检索、EPUB 与本 PDF 的最新版都在 $repo$
  ]
]

// ---------- 目录 ----------
#pagebreak()
#outline(title: [目录], depth: 1, indent: 1em)

// ---------- 正文 ----------
#pagebreak(weak: true)
#set page(header: running-head, footer: context align(center, text(8.5pt, fill: luma(120))[#counter(page).at(here()).first() / #counter(page).final().first()]))
#counter(page).update(1)

$body$
