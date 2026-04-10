# 测试集管理模块文档

## 概述

测试集管理模块用于为每道题目创建测试用例，验证评分脚本的准确性。核心流程：**建题 → 生成评分脚本 → 创建测试用例 → 验证评分 → 迭代优化**。

访问入口：`/test-cases`（独立页面，不嵌入首页 SPA）。

---

## 页面功能

### 一、总览视图

进入页面后默认显示所有题目的测试用例概览。

**统计卡片**（4 个）
- 题目总数、测试用例总数、整体通过率、平均误差

**筛选工具栏**
- 关键词搜索：按题目标题模糊匹配
- 状态筛选：已验证 / 待验证 / 未通过
- 科目筛选：仅管理员可见，科目老师自动锁定本科目
- 刷新按钮

**批量操作**
- 勾选多道题目 → 批量验证（逐题运行评分，容差固定 1.0）

**概览表格**

| 列 | 说明 |
|---|---|
| 题目标题 | 超长截断显示 |
| 科目 | 科目名称 |
| 用例/脚本 | 用例总数 + 各类型分布（如 `3AI/1人工/1真实`）+ 评分脚本状态 |
| 通过率 | 进度条，颜色随通过率变化（绿/橙/红） |
| 验证状态 | 平均误差 + 最后验证时间 |
| 操作 | 管理（进入详情）、验证（直接验证）、清空（删除该题所有用例） |

### 二、详情视图

点击"管理"进入单题详情，左右分栏布局。

**左侧 — 测试用例管理**

- 题目信息栏：标题、科目、满分、评分脚本状态及版本号
- 搜索框：按描述和答案内容搜索用例
- 添加用例按钮：弹窗填写
- 批量删除：勾选多个用例后操作
- 用例表格列：描述、类型、期望/实际分、状态、答案预览、操作

**右侧 — 验证控制 + 结果**

- 容差设置（0~10 分，步长 0.5，默认 1.0）
- 运行验证按钮（带进度条）
- 验证结果：4 个统计指标 + 逐用例结果表格（期望分、实际分、误差、通过/未通过、AI 评语）

**添加/编辑用例弹窗**

| 字段 | 说明 |
|---|---|
| 描述 | 用例简要说明，如"满分答案"、"要点不全" |
| 类型 | AI生成 / 人工模拟 / 真实答卷（见下文） |
| 期望分数 | 0 到该题满分，步长 0.5 |
| 考生答案 | 粘贴答案文本 |

---

## 用例类型（case_type）

| 值 | 标签 | 含义 | 用途 |
|---|---|---|---|
| `ai_generated` | AI生成（蓝灰） | AI 大模型自动生成的模拟作答 | 开发阶段批量生成，覆盖多种得分梯度和作答风格 |
| `simulated` | 人工模拟（橙色） | 人工手动编写的模拟作答 | 老师构造边界用例、特殊场景 |
| `real` | 真实答卷（红色） | 来自真实考试的考生答卷 | **保留用于最终验收测试**，不参与日常验证 |

---

## 角色权限

| 角色 | 识别方式 | 权限 |
|---|---|---|
| 管理员 | localStorage `ai_grading_role = 'admin'` | 查看所有科目数据，显示科目筛选下拉框 |
| 科目老师 | localStorage `ai_grading_role = 'teacher'` + `ai_grading_current_subject` | 仅看到本科目数据，科目筛选隐藏，header 显示"科目 · 科目老师"标签 |

科目老师未选科目时自动重定向到 `/login`。

---

## API 接口

### 测试用例统计概览

```
GET /api/test-cases/overview?subject=xxx
```

返回所有题目的测试用例统计。`subject` 参数可选，不传返回全部。

**返回字段**

| 字段 | 类型 | 说明 |
|---|---|---|
| question_id | int | 题目 ID |
| title | str | 题目标题 |
| subject | str | 科目 |
| max_score | float | 满分 |
| has_rubric_script | bool | 是否有评分脚本 |
| total_cases | int | 用例总数 |
| ai_count | int | AI 生成数量 |
| simulated_count | int | 人工模拟数量 |
| real_count | int | 真实答卷数量 |
| passed_count | int | 验证通过数（误差 ≤ 1.0） |
| failed_count | int | 验证失败数（误差 > 1.0） |
| avg_error | float | 平均误差 |
| last_run_at | str | 最后验证时间 |

### 获取题目测试用例

```
GET /api/questions/{question_id}/test-cases
```

### 添加测试用例

```
POST /api/questions/{question_id}/test-cases
```

| 参数 | 必填 | 说明 |
|---|---|---|
| answer_text | 是 | 考生答案文本 |
| expected_score | 是 | 期望分数 |
| description | 否 | 描述 |
| case_type | 否 | 默认 `simulated`，可选 `ai_generated` / `simulated` / `real` |

### 更新测试用例

```
PUT /api/questions/{question_id}/test-cases/{test_case_id}
```

所有字段可选，缺省保留原值。支持回写评分结果（同时传 `last_actual_score` 和 `last_error`）。

### 删除测试用例

```
DELETE /api/questions/{question_id}/test-cases/{test_case_id}
```

### AI 自动生成测试用例

```
POST /api/questions/{question_id}/generate-test-cases
```

| 参数 | 必填 | 说明 |
|---|---|---|
| count | 否 | 生成数量，默认 7 |
| distribution | 否 | 分布策略：`gradient`（梯度）、`edge`（边界为主）、`middle`（中段为主）、`uniform`（均匀） |
| styles | 否 | 作答风格数组，默认 `["标准规范", "口语化", "要点遗漏"]`。可选：`标准规范`、`口语化`、`要点遗漏`、`偏题跑题`、`复制原文`、`空白作答` |
| extra | 否 | 补充要求 |

生成的用例 `case_type` 为 `ai_generated`。

### 验证评分脚本

```
POST /api/verify-rubric
```

| 参数 | 必填 | 说明 |
|---|---|---|
| question_id | 是 | 题目 ID |
| tolerance | 否 | 容差值，默认 1.0 |
| rubric_script | 否 | 传入时覆盖数据库中的脚本 |

对指定题目的所有测试用例逐个运行评分，对比实际分与期望分。通过标准：`abs(actual_score - expected_score) <= tolerance`。

**返回字段**

| 字段 | 类型 | 说明 |
|---|---|---|
| total_cases | int | 用例总数 |
| passed_cases | int | 通过数 |
| accuracy | float | 准确率（百分比） |
| mean_absolute_error | float | 平均绝对误差 |
| max_absolute_error | float | 最大绝对误差 |
| results | array | 逐用例结果（包含 expected_score、actual_score、error、passed、comment） |

### 生成评分脚本

```
POST /api/generate-rubric-script
```

| 参数 | 必填 | 说明 |
|---|---|---|
| content | 是 | 题目内容 |
| standardAnswer | 是 | 标准答案 |
| score | 否 | 满分，默认 10 |
| rubricRules | 否 | 评分规则 |
| rubricPoints | 否 | 得分要点 |
| aiRubric | 否 | 补充说明 |

---

## 数据库表

### test_cases

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增主键 |
| question_id | INTEGER | 关联题目 ID |
| answer_text | TEXT | 考生答案内容 |
| expected_score | REAL | 期望得分 |
| description | TEXT | 描述 |
| case_type | TEXT | 用例类型，默认 `simulated` |
| last_actual_score | REAL | 最近一次验证的实际得分 |
| last_error | REAL | 最近一次验证的绝对误差 |
| last_run_at | TIMESTAMP | 最近一次验证时间 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### rubric_script_history（评分脚本版本历史）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增主键 |
| question_id | INTEGER | 关联题目 ID |
| version | INTEGER | 版本号 |
| script_text | TEXT | 脚本内容 |
| avg_error | REAL | 验证后的平均误差 |
| passed_count | INTEGER | 验证通过数 |
| total_cases | INTEGER | 验证总用例数 |
| note | TEXT | 备注 |
| created_at | TIMESTAMP | 创建时间 |

---

## 典型工作流

```
1. 创建题目（题库管理 → 人工出题 / AI 批量出题）
       ↓
2. AI 生成评分脚本（题目编辑页 → "AI 生成评分脚本"）
       ↓
3. 生成测试用例（测试集管理 → 题目详情 → AI 生成 or 手动添加）
       ↓
4. 运行验证（设置容差 → 运行验证 → 查看准确率和误差）
       ↓
5. 迭代优化（准确率不达标 → 修改评分脚本 → 重新验证）
       ↓
6. 最终验收（导入真实答卷 → 验证 → 达标后上线）
```

---

## 相关文件

| 文件 | 路径 |
|---|---|
| 前端页面 | `templates/test-cases.html` |
| 后端路由 | `app/api_routes.py` |
| 数据库操作 | `app/models/db_models.py` |
| 页面入口路由 | `app/app.py`（`/test-cases`） |
