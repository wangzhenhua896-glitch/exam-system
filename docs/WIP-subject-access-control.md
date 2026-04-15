# WIP: 后端科目校验 — 交接文档

> 创建时间：2026-04-15
> 状态：已完成
> 分支：master（已提交 commit 364e303 + 本次完成）

## 目标

防止跨科目访问：老师只能操作本科目数据，不能通过 curl 等方式绕过前端直接访问其他科目。

## 设计方案

完整方案在：`/Users/peikingdog/.claude/plans/crystalline-forging-crab.md`

核心思路：Flask session（基于 SECRET_KEY 签名 cookie）+ `before_request` 统一校验 + 各端点科目访问控制。

## 已完成（全部）

### 1. `app/api_routes.py` — 登录/登出 + 辅助函数

- `POST /api/login` — 验证用户存在于 `users` 表，建立 session（username/subject/role）
- `POST /api/logout` — 清除 session
- `_check_subject_access(target_subject)` — admin 返回 True，teacher 检查 subject 是否匹配
- `_session_subject()` — admin 返回 None（全部），teacher 返回本科目

### 2. `app/app.py` — before_request 钩子

- 白名单放行：`/login`、`/admin`、`/`、`/static/*`、`/api/login`、`/api/users`
- 其他 `/api/*` 路由：session 中无 username → 返回 401

### 3. 已加科目校验的端点（全部完成）

| 端点 | 校验方式 | 行为 |
|------|---------|------|
| `GET /api/questions` | `_session_subject()` | 非 admin 强制用 session.subject 过滤，忽略请求参数 |
| `GET /api/questions/<id>` | `_check_subject_access` | 非 admin 不能查看其他科目题目（403） |
| `POST /api/questions` | `_check_subject_access` | 非 admin 不能为其他科目创建题目（403） |
| `PUT /api/questions/<id>` | `_check_subject_access` | 非 admin 不能修改其他科目题目（403） |
| `DELETE /api/questions/<id>` | `_check_subject_access` | 非 admin 不能删除其他科目题目（403） |
| `PUT /api/questions/<id>/workflow-status` | `_check_subject_access` | 非 admin 不能修改其他科目题目状态（403） |
| `GET /api/questions/<id>/children` | `_check_subject_access` | 非 admin 不能查看其他科目的子题（403） |
| `GET /api/questions/<id>/with-children` | `_check_subject_access` | 非 admin 不能查看其他科目题目（403） |
| `POST /api/grade` | `_check_subject_access` | 传 question_id 时校验题目所属科目（403）；无 question_id 时校验直接传的 subject（403） |
| `POST /api/batch` | `_check_subject_access` | 逐 item 校验，不匹配则跳过并记录错误 |
| `GET /api/stats` | `_session_subject()` | 非 admin 强制用 session.subject 过滤 |
| `GET /api/dashboard` | `_session_subject()` | 非 admin 强制用 session.subject 过滤 |
| `GET /api/export-rubric-scripts` | `_session_subject()` | 非 admin 强制用 session.subject |
| `GET /api/test-cases/overview` | `_session_subject()` | 非 admin 强制用 session.subject 过滤 |
| `GET /api/test-cases/all` | `_session_subject()` | 非 admin 强制用 session.subject 过滤 |
| `POST /api/questions/<id>/test-cases` | `_check_subject_access` | 非 admin 不能为其他科目题目添加测试用例（403） |
| `PUT /api/questions/<id>/test-cases/<tid>` | `_check_subject_access` | 非 admin 不能修改其他科目的测试用例（403） |
| `DELETE /api/questions/<id>/test-cases/<tid>` | `_check_subject_access` | 非 admin 不能删除其他科目的测试用例（403） |
| `POST /api/questions/<id>/generate-test-cases` | `_check_subject_access` | 非 admin 不能为其他科目题目生成测试用例（403） |
| `GET /api/syllabus` | `_session_subject()` | 非 admin 强制用 session.subject 过滤 |
| `GET /api/syllabus/<subject>/<type>` | `_check_subject_access` | 非 admin 不能查看其他科目大纲（403） |
| `POST /api/syllabus` | `_check_subject_access` | 非 admin 强制 subject = session.subject（403） |
| `DELETE /api/syllabus/<subject>/<type>` | `_check_subject_access` | 非 admin 不能删除其他科目大纲（403） |
| `GET /api/sensitive-words` | `_session_subject()` | 非 admin 强制用 session.subject 过滤 |
| `POST /api/sensitive-words` | `session.subject` | 非 admin 强制 subject = session.subject |
| `POST /api/sensitive-words/batch` | `session.subject` | 非 admin 强制覆盖 subject |
| `GET /api/history` | `_session_subject()` | 非 admin 只看本科目评分记录 |
| `POST /api/generate-rubric-points` | `session.subject` | 非 admin 强制用 session.subject |
| `POST /api/generate-rubric-script` | `session.subject` | 非 admin 强制用 session.subject |
| `POST /api/self-check-rubric` | `session.subject` | 非 admin 强制用 session.subject |
| `POST /api/evaluate-question` | `session.subject` | 非 admin 强制用 session.subject |
| `POST /api/auto-generate` | `session.subject` | 非 admin 强制用 session.subject |
| `POST /api/batch-check-consistency` | `session.subject` | 非 admin 强制用 session.subject |
| `POST /api/verify-rubric` | `_check_subject_access` | 非 admin 不能验证其他科目题目（403） |
| `POST /api/generate-answer` | `_check_subject_access` | 非 admin 不能为其他科目题目生成答案（403） |
| `GET /api/questions/<id>/answers` | `_check_subject_access` | 非 admin 不能查看其他科目答案（403） |
| `POST /api/questions/<id>/answers` | `_check_subject_access` | 非 admin 不能为其他科目添加答案（403） |
| `PUT /api/questions/<id>/answers/<aid>` | `_check_subject_access` | 非 admin 不能修改其他科目答案（403） |
| `DELETE /api/questions/<id>/answers/<aid>` | `_check_subject_access` | 非 admin 不能删除其他科目答案（403） |
| `GET /api/questions/<id>/script-history` | `_check_subject_access` | 非 admin 不能查看其他科目版本历史（403） |
| `POST /api/questions/<id>/script-rollback` | `_check_subject_access` | 非 admin 不能回退其他科目脚本（403） |
| `POST /api/questions/find-duplicates` | `_session_subject()` | 非 admin 只扫本科目 |
| `POST /api/questions/find-same-number` | `_session_subject()` | 非 admin 只扫本科目 |
| `POST /api/import-questions` | `_session_subject()` | 非 admin 导入的题目强制用 session.subject |
| `POST /api/import-word/confirm` | `_session_subject()` | 非 admin 导入的题目强制用 session.subject |

不做科目校验的端点（影响小或无科目概念）：
- `/api/providers` — 模型列表，无科目概念
- `/api/users` — 用户管理，白名单放行（登录页需要）
- `/api/grading-params` — 全局参数配置
- `/api/bugs` — 系统 bug 日志，诊断用
- `/api/check-consistency` — 单题一致性检查，基于请求体数据

### 4. `templates/login.html` — 前端改造

- `enterSystem()` 改为先调 `POST /api/login` 建立 session，再写 localStorage
- `goAdmin()` 改为调 `POST /api/login { username: 'admin' }` 建立 session

### 5. `static/js/shared.js` — 401 跳转

- `handleApiError` 中加 401 检测，自动跳转 `/login`

### 6. 验证测试（全部通过）

```
Test 1: No session → GET /api/questions → 401 ✓
Test 2: POST /api/login { username: 'english' } → success ✓
Test 3: GET /api/questions with session → 只返回英语题目(28题) ✓
Test 4: GET /api/questions?subject=politics → 仍只返回英语 ✓
Test 5: GET /api/stats → 只显示英语统计 ✓
Test 6: GET /api/dashboard → subject=english ✓
Test 7: GET /api/questions/<政治题ID> → 403 ✓
Test 8: POST /api/logout → success ✓
Test 9: After logout, GET /api/questions → 401 ✓
Test 10: GET /api/users without auth → success (白名单) ✓
Test 11: Admin login → 全科访问(62题/4科) ✓
Test 12: POST /api/syllabus with politics subject as english → 403 ✓
Test 13: POST /api/syllabus with english subject as english → success ✓
```
