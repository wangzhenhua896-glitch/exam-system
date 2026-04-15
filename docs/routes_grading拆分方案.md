# routes_grading.py 拆分方案

## 拆分目标

把 `routes_grading.py`（1025行）拆为三个职责清晰的文件，同时整理 `/grade` 函数内部结构。

---

## 文件拆分

### ① `routes_grade.py` — 单题评分
路由：`/providers`、`/grade`、`/models/available`

### ② `routes_batch.py` — 批量评分
路由：`/batch`（POST）、`/batch/<id>`（GET）

### ③ `routes_stats.py` — 统计报表
路由：`/history`、`/stats`、`/dashboard`

原 `routes_grading.py` 删除，`api_routes.py` 入口补充注册这三个新蓝图。

---

## `/grade` 函数内部整理

现在 `grade_answer()` 函数约490行，逻辑全堆在一起。整理后拆为5个私有函数，主函数只剩调用链。

```python
# 主函数（约50行）
def grade_answer():
    data = request.json
    question_info = _load_question(data)          # ① 加载题目
    precheck = _precheck_answer(...)              # ② 空答案+敏感词
    if precheck:
        return precheck                           #   直接返回0分
    grade_result = three_layer_grade(...)         # ③ 三层评分
    flags = _run_judgment(grade_result, ...)      # ④ 判别Agent
    record_id = _save_record(grade_result, ...)   # ⑤ 保存+一致性校验
    return jsonify(...)
```

五个私有函数放在同一文件（`routes_grade.py`）里，不新建模块：

| 函数 | 职责 | 大约行数 |
|------|------|----------|
| `_load_question(data)` | 从DB加载题目、rubric、满分答案、子题采分点 | ~70行 |
| `_precheck_answer(answer, subject, ...)` | 空答案判0分、敏感词判0分，返回 response 或 None | ~80行 |
| `_build_result(grade_result, subject, max_score)` | 处理英语采分点命中、fallback兜底、策略覆盖 | ~50行 |
| `_run_judgment(result, answer, max_score, subject)` | 证据验证、短答案高分检测、全满分检测 | ~60行 |
| `_save_record(result, flags, ...)` | 保存评分记录、一致性校验更新flags | ~50行 |

---

## 注意事项

- `routes_batch.py` 里批量评分的题目加载逻辑与单题评分高度重复，可直接复用 `_load_question()`，两处共享一份代码
- 三个文件都从 `api_shared.py` 导入 `api_bp`、`grading_engine`、`_check_subject_access`、`_session_subject`，不新增共享变量
- `/grade` 函数的 OpenAPI 文档注释（约125行）可在整理时缩减到20行，大幅减少视觉噪音

---

## 整理后预计行数

| 文件 | 预计行数 |
|------|----------|
| `routes_grade.py` | ~380行 |
| `routes_batch.py` | ~160行 |
| `routes_stats.py` | ~320行 |
| 合计 | ~860行（原1025行） |
