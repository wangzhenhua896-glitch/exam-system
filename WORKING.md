# Agent 协作公告板

> **所有 Agent 和测试电脑的使用规则：**
> 1. 开始前先 `git pull` 拉取最新内容，看本文件
> 2. 写代码的 Agent：把自己要改的文件写到"正在进行"，推送后再开始改
> 3. 干完之后，把自己的记录删掉，推送更新
> 4. 测试电脑：发现问题写到"测试反馈"，通过的写到"测试通过"

---

## 正在进行

| Agent | 改动文件 | 说明 |
|-------|---------|------|
| （空闲）| | |

---

## 测试反馈（测试电脑填写）

| 时间 | 功能 | 问题描述 |
|------|------|------|
| （暂无）| | |

---

## 测试通过（测试电脑填写）

| 时间 | 功能 | 备注 |
|------|------|------|
| 2026-04-15 | 英语编辑器第3步评分细则卡片视图 | Playwright 自动化测试通过：卡片渲染、采分点标签、原始脚本收起、无控制台错误 |

---

## 文件归属建议（减少冲突）

| 文件 | 负责方向 |
|------|------|
| `app/english_prompts.py` | 英语 Agent |
| `static/js/englishEditCore.js` | 英语 Agent |
| `static/js/englishEdit{Helpers,AI,ValidateSave}.js` | 英语 Agent |
| `app/api_routes.py` 中 `/english/` 接口 | 英语 Agent |
| `app/api_routes.py` 其余部分 | 后端 Agent |
| `app/models/db_models.py` | 后端 Agent |
| `templates/question-bank.html` | **当前 Agent 正在改第3步区域（520行起）** |
