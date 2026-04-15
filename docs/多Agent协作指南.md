# 多 Agent 协作指南

## 场景

| 场景 | 同步机制 | 冲突风险 |
|------|---------|---------|
| 不同电脑 | `WORKING.md` + `git pull/push` | 低（有 git 延迟检测） |
| 同一台电脑 | `git worktree` 隔离 | 零（完全独立目录） |

---

## 不同电脑协作

### 每次开工前

```bash
git pull                          # 拉取最新代码
cat WORKING.md                    # 查看其他 Agent 正在改什么
```

### 开始工作

```bash
# 把自己要改的文件写进 WORKING.md
vim WORKING.md                    # 添加记录
git add WORKING.md && git commit -m "chore: Agent-B 开始改 api_routes.py"
git push
```

### 完成后

```bash
# 从 WORKING.md 删除自己的记录
vim WORKING.md
git add -A && git commit -m "feat: xxx"
git push
```

### 推送前防冲突

```bash
git pull --rebase                 # 先 rebase 再推
# 如果有冲突，手动解决后 git rebase --continue
```

### 文件归属（避免改同一文件）

| 文件/目录 | 负责 Agent |
|-----------|-----------|
| `app/english_*.py`, `app/english_prompts.py` | 英语 Agent |
| `static/js/englishEditCore.js` | 英语 Agent |
| `/api/english/` 接口 | 英语 Agent |
| `app/api_routes.py`（非英语部分） | 后端 Agent |
| `app/qwen_engine.py`, `app/three_layer_grader.py` | 后端 Agent |
| `app/models/db_models.py` | 后端 Agent |
| `templates/question-bank.html` | **协商后改** |
| 其他模板页面（question-edit/dedup/import 等） | 前端 Agent |

---

## 同一台电脑协作（worktree 隔离）

### 原理

`git worktree` 让同一个仓库有多个工作目录，每个 Agent 在独立目录操作，互不影响。

```
/Users/peikingdog/allexam.sys/question-bank/ai-grading-system/     ← 主目录 (master)
/Users/peikingdog/allexam.sys/question-bank/ai-grading-system/.claude/worktrees/agent-b/   ← Agent B 的 worktree
/Users/peikingdog/allexam.sys/question-bank/ai-grading-system/.claude/worktrees/agent-c/   ← Agent C 的 worktree
```

### Agent B 创建 worktree

```bash
cd /Users/peikingdog/allexam.sys/question-bank/ai-grading-system

# 创建 worktree，基于当前分支新建分支
git worktree add .claude/worktrees/agent-b feature/agent-b-work

# Agent B 的 Claude Code 在这个目录下启动
cd .claude/worktrees/agent-b
# 在这里启动 Claude Code
```

### Agent B 完成后合并回主目录

```bash
# 回到主目录
cd /Users/peikingdog/allexam.sys/question-bank/ai-grading-system

# 合并 Agent B 的分支
git merge feature/agent-b-work

# 合并完成后清理 worktree
git worktree remove .claude/worktrees/agent-b
git branch -d feature/agent-b-work
```

### 查看所有 worktree

```bash
git worktree list
```

### 多个 Agent 同时工作

```bash
# Agent B：改后端
git worktree add .claude/worktrees/agent-b feature/backend-refactor

# Agent C：改前端
git worktree add .claude/worktrees/agent-c feature/frontend-cleanup

# 各自在独立目录工作，互不干扰
# 完成后分别 merge
```

### 注意事项

- worktree 之间**共享 git 对象**（commit/branch），但工作目录完全隔离
- 不能在两个 worktree 中 checkout 同一个分支（会报错）
- 合并时如果改了同一文件，走正常 git 冲突解决流程
- `.env`、`data/` 等文件在 worktree 间共享（是同一个物理文件）

---

## 快速参考

### 不同电脑：开始工作

```bash
git pull && cat WORKING.md
# 确认没有冲突后
vim WORKING.md  # 添加：Agent-B: 改 app/api_routes.py, app/qwen_engine.py
git add WORKING.md && git commit -m "chore: Agent-B 开始工作" && git push
```

### 同一台电脑：开始工作

```bash
cd /Users/peikingdog/allexam.sys/question-bank/ai-grading-system
git worktree add .claude/worktrees/agent-b feature/my-task
cd .claude/worktrees/agent-b
# 在这里启动 Claude Code
```

### 同一台电脑：完成工作

```bash
cd /Users/peikingdog/allexam.sys/question-bank/ai-grading-system
git merge feature/my-task
git worktree remove .claude/worktrees/agent-b
git branch -d feature/my-task
```
