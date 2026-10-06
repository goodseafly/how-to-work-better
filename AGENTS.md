# AGENTS.md

这个目录是《高性价比职场指南》的正文。

- **改这本书**（增删条目、改正文、动构建与检查脚本）：规则全在 [CLAUDE.md](CLAUDE.md) 里，全部适用，先读完再动手。文件名叫 CLAUDE.md 只是历史原因，内容与工具无关。
- **用这本书回答问题**（有人问该不该做、值不值、怎么选、出事了先做什么、能领哪笔钱、犯不犯法）：按 [skills/workplace-decision-guide/SKILL.md](skills/workplace-decision-guide/SKILL.md) 执行，先查条目再答，答复里注明出自第几节第几条。装到别的目录去用的办法见 [skills/workplace-decision-guide/README.md](skills/workplace-decision-guide/README.md)。
- **改完正文之后**：重跑三个检查器（`tools/check-body.py`、`tools/check-refs.py`、`tools/full-audit.py`），再按需重建四样成品（`tools/build-offline.py`、`tools/build-index.py`、`tools/build-pdf.py`、`tools/build-epub.py`）。动了 README 或成品，`full-audit.py` 要连渲染一起跑（默认就会跑，需要 pandoc；只想跑源码层用 `--source-only`）。
