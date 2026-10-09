# 职场决策 skill（workplace-decision-guide）

让 AI 助手照《高性价比职场指南》回答具体问题：该不该做、值不值、怎么选、出事了先做什么、能领哪笔钱、这么干违法不违法、被裁被欠薪怎么办。

它做的事只有一件：**先把相关条目从正文里查出来，再照书的算账方式排序回答**，每条注明出自第几节第几条。查不到就说查不到，不凭记忆编数字。

规则全在 [SKILL.md](SKILL.md) 里，两个工具共用同一个文件，不维护两份。

## 装到 Claude Code

在这个目录（或它的上层）里开 Claude Code，不用装——`.claude/skills/workplace-decision-guide/` 指向这份规则即可。

想在任何目录下都能用，把整个目录复制到个人 skill 目录：

```bash
mkdir -p ~/.claude/skills && cp -r /path/to/高性价比职场指南/skills/workplace-decision-guide ~/.claude/skills/
```

之后直接问「被裁了先做什么」「公司让我签自愿放弃社保，签不签」就会触发；也可以显式说「用 workplace-decision-guide 回答」。

## 装到 Codex

在这个目录里开 Codex，不用装——根目录的 `AGENTS.md` 已经把它指出来了。

想在任何目录下都能用，复制到 Codex 的个人 skill 目录 `~/.agents/skills`：

```bash
mkdir -p ~/.agents/skills && cp -r /path/to/高性价比职场指南/skills/workplace-decision-guide ~/.agents/skills/
```

之后直接问问题就会按描述自动触发，也可以输入 `$workplace-decision-guide` 显式调用。注意是 `$` 不是 `/`，新版 Codex 输入 `/workplace-decision-guide` 会报 `Unrecognized command`。

## 正文从哪来

skill 只读本地的 `book/` 和 `README.md`，把上面的目录路径给到它即可。仓库地址：https://github.com/goodseafly/how-to-make-work-pay （公开，CC BY 4.0）。取不到正文就如实说取不到，不替代正文。

## 改动须知

SKILL.md 里不留任何会跟着正文漂的清单和数值：节的清单去读 README 的「这本书想回答的问题」表，性价比档的算法去读 `index.html` 里的 `COST_W` 和 `e.ratio` 两行。所以增删节、改档位规则都不用动这个目录。
