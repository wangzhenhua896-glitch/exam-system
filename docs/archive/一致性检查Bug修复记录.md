# 一致性检查 Bug 修复记录

> 记录时间：2026-04-12
> 涉及功能：题库管理 → 单题处理 → 一致检查
> 涉及文件：`templates/question-bank.html`、`app/api_routes.py`

---

## 概述

一致检查功能的目的是：当用户编辑题目时，检测题干、答案、评分规则、满分等字段之间是否存在不一致（如满分 8 分但分数分布合计 10 分）。上线后发现 **5 个 Bug**，导致检查该报错时不报错、修复后不生效、前端崩溃等问题。

---

## Bug 1：一致检查该报错但不报错

### 现象

题号 10 的 max_score 实际为 8 分，但分数分布合计 10 分。点"一致检查"后，系统报告"未发现问题"——明显应该报错。

### 根因

前端加载题目编辑时，`loadQuestionToForm` 函数中有两行逻辑：

```javascript
// 旧代码（已删除）
// 用分数分布之和覆盖 max_score
questionForm.score = rubric_points_sum;  // 从 8 改成 10
```

这行代码把 `questionForm.score` 从数据库原始值（8）覆盖成了分数分布之和（10）。

随后 `runConsistencyCheck` 把 `questionForm.score` 作为 `maxScore` 发给后端：

```javascript
const payload = {
    // ...
    maxScore: questionForm.score  // 此时已被覆盖为 10
};
```

后端比较时：推断满分 = 原文满分 = 8，表单满分 = 10。**本来应该报 `form_score_wrong`**，但因为表单和推断值不同，后端的推断逻辑又以分数分布之和（10）为推断值，于是推断值 == 表单值 == 10，检查通过。

### 修复

删除 `loadQuestionToForm` 中用分数分布覆盖 `max_score` 的代码，改为保留数据库原始值：

```javascript
// 不再用分数分布之和覆盖 max_score，保留数据库原始值以便一致检查发现问题
```

### 数据流对比

| 步骤 | 修复前 | 修复后 |
|------|--------|--------|
| 数据库 max_score | 8 | 8 |
| 加载到表单 | 8 → 被覆盖为 10 | 8（保留原始值） |
| 发给后端 maxScore | 10 | 8 |
| 后端推断满分 | 10（用分数分布之和） | 8（用原文标注满分） |
| 推断 vs 表单 | 10 == 10 → 通过 | 8 == 8 → 通过 |
| 原文 8 vs 分布 10 | — | 发现不一致 → 报错 ✓ |

> 注：修复后推断逻辑也改为以原文标注满分（8）为权威值，这样 `form_score_wrong` 的报错信息才是"表单应该是 8 分"而非"应该是 10 分"。

---

## Bug 2：推断满分用错了数据源

### 现象

即使 Bug 1 修复后能报错了，但报错信息说"应该是 10 分，把表单改成 10"——而正确的满分是 8 分（原文标注为准）。

### 根因

后端 `check_consistency` 中，当原文满分（8）和分数分布之和（10）不一致时：

```python
# 旧代码
else:
    inferred_score = rubric_total  # 错误：用了分数分布之和（10）
```

用分数分布之和作为推断值，导致建议用户把表单从 8 改成 10——方向反了。

### 修复

```python
# 新代码
else:
    inferred_score = orig_total_score  # 正确：原文标注满分是权威值
```

### 设计原则

**原文标注满分是权威数据源**。分数分布是从原文派生的，如果两者不一致，应以原文为准，检查分数分布是否有误。

---

## Bug 3：rubricPoints 类型错误导致后端崩溃

### 现象

调用 `/api/check-consistency` 时报 500 错误，日志显示 `'list' object has no attribute 'strip'`。

### 根因

前端传 `rubricPoints` 有两种格式：
- **字符串**：用户手动编辑时，`questionForm.rubricPoints` 是 textarea 的值（字符串）
- **数组**：AI 生成或某些操作后，`questionForm.rubricPoints` 可能是对象数组（如 `[{text:"尊老爱幼", score:1.6}, ...]`）

后端直接调 `.strip()` 没判断类型：

```python
# 旧代码
rubric_points = data.get('rubricPoints', '').strip()  # 如果是 list 就崩
```

### 修复

```python
# 新代码
rubric_points_raw = data.get('rubricPoints', '')
if isinstance(rubric_points_raw, list):
    rubric_points = '\n'.join(
        f"{p.get('text', p.get('label', ''))} ({p.get('score', 0)}分)"
        for p in rubric_points_raw if isinstance(p, dict)
    )
else:
    rubric_points = (rubric_points_raw or '').strip()
```

### 根本原因

前端表单字段 `rubricPoints` 没有统一的数据类型——有时是字符串，有时是数组。后端没有防御性处理。

### 建议

前端应在保存/发送前统一转为字符串，或后端所有入口都做类型兼容。当前采用后者（后端兼容两种格式）。

---

## Bug 4：form_score_wrong 类型前端不识别

### 现象

后端返回了类型为 `form_score_wrong` 的 issue，前端弹窗显示了问题描述，但点"确定"修复后，表单的 score 没有变化。

### 根因

`showNextIssue` 的修复逻辑原来只处理 `orig_score_mismatch`：

```javascript
// 旧代码
if (issue.type === 'orig_score_mismatch' && issue.original_value) {
    questionForm.score = parseFloat(issue.original_value);
}
```

后端新增的 `form_score_wrong` 类型不在条件判断中，所以即使 `original_value` 有值（如 "8"），也不会写入表单。

### 修复

```javascript
// 新代码
if ((issue.type === 'orig_score_mismatch' || issue.type === 'form_score_wrong') && issue.original_value) {
    questionForm.score = parseFloat(issue.original_value);
}
```

同时 `canFix` 判断也加上了新类型：

```javascript
const canFix = !!issue.original_value || issue.type === 'orig_score_mismatch' || issue.type === 'form_score_wrong';
```

### 根本原因

前后端类型定义不同步。后端新增了 issue type，前端没有对应处理。缺少统一的类型枚举或契约。

---

## Bug 5：修复后只改了数据库，表单没更新

### 现象

用户点"确定修改"后，数据库中的 max_score 已经更新（如从 10 改成 8），但页面表单中的满分还是 10。不刷新页面再次检查，又会报错。用户感觉"确定修改没生效"。

### 根因

`showNextIssue` 中点"确定"后，虽然执行了 `questionForm.score = parseFloat(issue.original_value)` 更新了本地表单，**但紧接着调用了 `saveQuestion()`**，`saveQuestion` 会：

1. 把更新后的表单值 PUT 到后端 → 数据库更新成功
2. 调用 `resetForm()` → 清空表单
3. 调用 `loadQuestions()` → 刷新题目列表

问题出在 `resetForm()` 把表单清空了，而用户看到的是清空后的状态（默认值 10），不是刚保存的值。

### 当前状态

此问题在本次修复中**未完全解决**。`saveQuestion` 成功后调了 `resetForm()` 清空表单，如果用户要继续编辑同一题，需要重新点击题目加载。这是 `saveQuestion` 的设计——保存后回到列表视图。

### 如果要进一步优化

可在 `saveQuestion` 成功后，对当前编辑的题目重新调用 `loadQuestionToForm`，而非 `resetForm`：

```javascript
// 可选优化（当前未采用）
if (viewMode.value === 'edit' && editingQuestionId.value) {
    await loadQuestionToForm(editingQuestionId.value);
} else {
    resetForm();
}
```

---

## 关联数据事故：题号 10（question_id=22）原文丢失

### 过程

1. 测试 PUT `/api/questions/22` 时没传 `original_text` 字段
2. 后端 `update_question` 对未传的字段用 `data.get('original_text')` → `None`
3. `db_models.update_question` 中 `original_text=None` 被写入数据库，覆盖了原文
4. 尝试用 `git checkout` 恢复 → 数据库是二进制文件，git 版本极旧（只有 4 题），恢复失败
5. 尝试用 `.bak` 备份恢复 → 备份是在数据丢失后创建的，也是空的
6. 最终从 Word 文档 `简答题（思政汇总）.docx` 手动恢复

### 教训

| 教训 | 对策 |
|------|------|
| PUT API 没传的字段会覆盖为 None | 操作前备份数据库 |
| git 不能恢复数据库（二进制 + 版本旧） | 用 `.bak` 文件备份，且备份在操作前创建 |
| 备份在操作后创建 = 无效备份 | 操作前 `cp db db.bak`，验证无误前不删备份 |
| 恢复后只看一两个字段就说"已恢复" | 恢复后逐字段对比备份和当前数据 |

---

## 修复总结

| Bug | 位置 | 改动 |
|-----|------|------|
| 该报错不报错 | `question-bank.html` loadQuestionToForm | 删除分数分布覆盖 max_score 的代码 |
| 推断满分用错数据源 | `api_routes.py` check_consistency | 改用 orig_total_score 作为权威值 |
| rubricPoints 类型崩溃 | `api_routes.py` check_consistency | 增加 isinstance 判断，兼容 list 和 str |
| form_score_wrong 不识别 | `question-bank.html` showNextIssue | canFix 和 auto-fix 逻辑增加该类型 |
| 修复后表单没更新 | `question-bank.html` showNextIssue | 已在 showNextIssue 中更新表单值（resetForm 是保存后行为） |

---

## 防范措施

### 1. 前后端类型契约

后端新增 issue type 时，前端必须同步处理。建议：
- 在文档中维护 `issue_type` 枚举列表
- 前端 `showNextIssue` 对未知 type 打 console.warn 提醒

### 2. API 参数完整性

`PUT /api/questions/{id}` 应只更新传入的字段，未传入的字段保留原值：

```python
# 当前实现（有风险）
original_text=data.get('original_text'),  # 未传时为 None，会覆盖数据库

# 改进方案（建议）
original_text=data.get('original_text', existing.get('original_text')),
# 未传时保留数据库原值
```

### 3. 表单字段类型统一

`questionForm.rubricPoints` 应始终为字符串。AI 生成结果写入前，应先转为字符串格式。

### 4. 操作前备份铁律

任何涉及数据库修改的操作前，必须执行：
```bash
cp data/exam_system.db data/exam_system.db.bak
```
验证无误前不删除备份。恢复时用 `.bak` 文件，不用 `git checkout`。
