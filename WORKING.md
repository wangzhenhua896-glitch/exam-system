# Agent 协作公告板

> 每个 Agent 开始干活前：
> 1. 先 `git pull` 拉取最新内容
> 2. 查看下面"正在进行"的内容，避开别人在改的文件
> 3. 把自己要改的文件写到"正在进行"里，推送到 Gitea
> 4. 干完之后，把自己的记录删掉，再推送

---

## 正在进行

（目前无人作业）

---

## 文件归属建议（减少冲突）

| 文件 | 负责方向 |
|------|------|
| `app/english_prompts.py` | 英语 Agent |
| `static/js/englishEditCore.js` | 英语 Agent |
| `app/api_routes.py` 中 `/english/` 接口 | 英语 Agent |
| `app/api_routes.py` 其余部分 | 后端 Agent |
| `app/models/db_models.py` | 后端 Agent |
| `templates/question-bank.html` | 协商后再动 |
