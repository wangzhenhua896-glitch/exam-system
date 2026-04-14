# 2026-04-12 14:30 变更记录

## 本次对话修改内容

### 1. 评分页面：结果面板折叠时输入区铺满
- **文件**: `dist/index.html` 第98行
- **改动**: 左侧输入区宽度逻辑增加 `!resultCollapsed` 判断，结果面板折叠时输入区自动变为 `100%` 铺满
- **原始**: `(grading || gradeResult ? '400px' : '100%')`
- **改为**: `((grading || gradeResult) && !resultCollapsed ? '400px' : '100%')`

### 2. 评分页面：评分脚本字号切换按钮
- **文件**: `dist/index.html` 按钮栏, `static/js/useApp.js` 新增 ref + 函数
- **改动**: 在"复制"和"铺满"按钮之间加了字号切换按钮 `A 14px`，点击在 12px → 14px → 16px 三档循环
- **useApp.js**: 新增 `rubricFontSize` ref（默认14）和 `toggleRubricFontSize()` 函数

### 3. 评分页面：评分脚本内容滚到文首
- **文件**: `dist/index.html` 第138行, `static/js/useApp.js`
- **改动**: 给只读 textarea 加 `ref="rubricTextareaRef"`，`watch(selectedQuestion)` 后 `nextTick` 将 `scrollTop` 设为 0

### 4. 题库管理：评分脚本 → 评分约定（UI标签全面替换）
- **文件**: `templates/question-bank.html`
- **替换位置**: 仪表盘标签、表格列头、详情弹窗标题、按钮文字（AI 生成约定、验证约定）、导出按钮、弹窗标题（版本历史、验证、预览）、自动出题描述、成功/失败提示

### 5. 题库管理：按钮顺序调整
- **文件**: `templates/question-bank.html` 第416-421行
- **改动**: "一致检查"和"导出评分约定"互换位置
- **新顺序**: 批量导入Excel → 去重处理 → 合并同题 → 一致检查 → 导出评分约定

### 6. 题库管理：详情弹窗间距缩小
- **文件**: `templates/question-bank.html` 第470-495行
- **改动**: 各区块 `margin-top`: 12px→6px, 标题 `margin-bottom`: 6px→3px, 内容 `padding`: 10px→6px 10px

### 7. 题库管理：编辑表单区块间距缩小
- **文件**: `templates/question-bank.html` 基本信息/原题/评分规则区块
- **改动**: 区块 `margin-bottom`: 24px→8px, collapse `margin-bottom`: 12px→4px

### 8. 题库管理：评分脚本内容滚到文首
- **文件**: `templates/question-bank.html`
- **改动**: textarea 加 `ref="rubricScriptRef"`，`watch(questionForm.rubricScript)` 后 `nextTick` 重置 scrollTop

### 9. 题库管理：新增"约定自查"功能
- **后端** `app/api_routes.py`: 新增 `POST /api/self-check-rubric` 端点（第1796-1909行）
  - 接收题目内容、标准答案、当前约定
  - AI 按8项标准审查（自包含性、确定性语言、分值明确、关键词、反作弊、输出格式、逻辑矛盾、边界情况）
  - 返回 issues 列表 + improved_script
- **前端** `templates/question-bank.html`:
  - 按钮栏新增橙色"约定自查"按钮（AI 生成约定和验证约定之间）
  - 自查结果展示面板（问题列表 + 折叠查看完善版 + 应用/关闭按钮）
  - 新增 `selfChecking`/`selfCheckResult` ref, `selfCheckRubric()`/`applyImprovedScript()` 函数

## 涉及文件清单
| 文件 | 变更类型 |
|------|----------|
| `dist/index.html` | 字号按钮、折叠铺满、滚动修复 |
| `static/js/useApp.js` | rubricFontSize、rubricTextareaRef、watch |
| `templates/question-bank.html` | 标签替换、间距、自查功能、按钮排序 |
| `app/api_routes.py` | 新增 self-check-rubric 端点 |
