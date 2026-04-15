# 交接文档 — 2026-04-15 会话结束

> 分支：master
> 最新 commit：`ece1dff`（已在 Gitea）

## 本次会话完成的工作

### 1. 后端科目校验（全部完成）
- 40+ 个 API 端点加了科目访问控制
- 非 admin 只能操作本科目数据，跨科目 → 403，无 session → 401
- 前端 login.html 改为调 POST /api/login 建立服务端 session
- shared.js 加 401 自动跳转登录页
- 改动文件：`app/api_routes.py`、`app/app.py`、`templates/login.html`、`static/js/shared.js`
- 交接文档：`docs/WIP-subject-access-control.md`（已标记完成）

### 2. LLM 调用 timeout 保护
- `qwen_engine.py` 3 处 OpenAI() 构造加 `timeout=60.0`
- `config_routes.py` 2 处 OpenAI() 构造加 `timeout=30.0`
- 超时后触发已有的 3 次重试机制（指数退避）

### 3. 文档更新
- `docs/PROJECT_SUMMARY.md` — "无权限控制"标记为已实现

## P0 全部完成

| P0 项 | 状态 |
|------|------|
| autoGeneratePoints 悬空引用 | 已修复 |
| 批量评分绕过三层评分 | 已修复（调 three_layer_grade） |
| LLM 无超时 | **本次修复** |

## 推送规则
- **只推 Gitea**，不推 GitHub
- 推送前 `git stash && git pull gitea master --rebase && git stash pop && git push gitea master`

## 下一步工作（待排优先级）

参见本文件开头的"下一步工作"列表，主要方向：
1. 清理伪 async（`async def` / `asyncio.gather` → `ThreadPoolExecutor`）
2. 评分脚本 Prompt 优化（等价表述表）
3. 单元测试（核心评分函数）
4. 双 Agent 架构 / 多样本中位数打分（架构升级）

## 其他 Agent 活动

本次会话中 Gitea 上有其他 Agent 推了新文件：
- `docs/api_routes拆分方案.md` — api_routes.py 拆分方案（4316 行太臃肿）
- 另有"英语编辑器 7 项体验优化"等提交

新会话请先 `git pull gitea master` 再开始工作。
