# WIP: 后端科目校验 — 交接文档

> 创建时间：2026-04-15
> 状态：进行中，需在新对话中继续
> 分支：master（已提交 commit 364e303）

## 目标

防止跨科目访问：老师只能操作本科目数据，不能通过 curl 等方式绕过前端直接访问其他科目。

## 设计方案

完整方案在：`/Users/peikingdog/.claude/plans/crystalline-forging-crab.md`

核心思路：Flask session（基于 SECRET_KEY 签名 cookie）+ `before_request` 统一校验 + 各端点科目访问控制。

## 已完成

### 1. `app/api_routes.py` — 登录/登出 + 辅助函数（新增 ~50 行）

- `POST /api/login` — 验证用户存在于 `users` 表，建立 session（username/subject/role）
- `POST /api/logout` — 清除 session
- `_check_subject_access(target_subject)` — admin 返回 True，teacher 检查 subject 是否匹配
- `_session_subject()` — admin 返回 None（全部），teacher 返回本科目

### 2. `app/app.py` — before_request 钩子（新增 ~16 行）

- 白名单放行：`/login`、`/admin`、`/`、`/static/*`、`/api/login`
- 其他 `/api/*` 路由：session 中无 username → 返回 401

### 3. `api_routes.py` — 已加科目校验的端点

| 端点 | 校验方式 | 行为 |
|------|---------|------|
| `GET /api/questions` | `_session_subject()` | 非 admin 强制用 session.subject 过滤，忽略请求参数 |
| `GET /api/questions/<id>` | `_check_subject_access` | 非 admin 不能查看其他科目题目（403） |
| `POST /api/questions` | `_check_subject_access` | 非 admin 不能为其他科目创建题目（403） |
| `PUT /api/questions/<id>` | `_check_subject_access` | 非 admin 不能修改其他科目题目（403） |
| `DELETE /api/questions/<id>` | `_check_subject_access` | 非 admin 不能删除其他科目题目（403） |
| `POST /api/grade` | `_check_subject_access` | 传 question_id 时校验题目所属科目（403） |
| `POST /api/batch` | `_check_subject_access` | 逐 item 校验，不匹配则跳过并记录错误 |

## 未完成

### 4. 其他端点科目校验

以下端点尚未加校验，需要在新对话中处理：

- `GET /api/stats` — 非 admin 应强制用 session.subject 过滤
- `GET /api/dashboard` 或 `GET /api/dashboard/overview` — 同上
- `GET /api/export-rubric-scripts` — 同上
- `GET /api/test-cases/overview` — 同上
- `GET /api/syllabus` — 同上
- `POST /api/syllabus` — 非 admin 强制 subject = session.subject
- `POST /api/ai-generate` — 非 admin 强制 subject = session.subject
- `GET/POST /api/sensitive-words` — 同上

**方法：** 找到每个端点中读取 subject 参数的位置，加 `_session_subject()` / `_check_subject_access()` 校验。

### 5. `templates/login.html` — 前端改造

当前 `enterSystem()` 只写 localStorage，不调后端。需要改为：

```js
const enterSystem = async () => {
    // ... 验证逻辑不变 ...
    const { data } = await axios.post('/api/login', { username: selectedSubject.value });
    if (data.success) {
        localStorage.setItem(ROLE_KEY, data.data.role);
        localStorage.setItem(CURRENT_SUBJECT_KEY, data.data.subject);
        localStorage.setItem(TEACHER_NAME_KEY, name);
        window.location.href = '/management?t=' + Date.now();
    }
};
```

`goAdmin()` 同理：

```js
const goAdmin = async () => {
    const { data } = await axios.post('/api/login', { username: 'admin' });
    if (data.success) {
        localStorage.setItem(ROLE_KEY, 'admin');
        localStorage.removeItem(CURRENT_SUBJECT_KEY);
        localStorage.removeItem(TEACHER_NAME_KEY);
        window.location.href = '/admin';
    }
};
```

### 6. `static/js/shared.js` — 401 跳转

在 `handleApiError` 函数中加 401 处理：

```js
if (error.response && error.response.status === 401) {
    window.location.href = '/login?t=' + Date.now();
    return;
}
```

### 7. 验证测试

用 curl 或 Playwright 验证：
1. 不带 session 访问 `GET /api/questions` → 401
2. `POST /api/login { username: 'english' }` → success + cookie
3. 带 cookie `GET /api/questions` → 只返回英语题目
4. 带 cookie `GET /api/questions?subject=politics` → 仍只返回英语
5. 带 cookie `DELETE /api/questions/<政治题ID>` → 403
6. `POST /api/logout` → 清除 session

### 8. 文档更新

- CLAUDE.md：补充 session 认证机制说明
- PROJECT_SUMMARY.md：安全架构更新

## 注意事项

- `get_user(username)` 已存在于 `db_models.py`（line 1127），直接用
- `users` 表预置用户：admin/politics/chinese/english/math/history/geography/physics/chemistry/biology
- admin 的 subject 为 NULL，`_session_subject()` 返回 None 表示全库访问
- Flask session 默认 cookie 名 `session`，SameSite=Lax，前端 axios 默认带 cookie
- `config_routes.py` 也有 `/api/config/*` 路由，before_request 已覆盖，如需要也可加科目校验
