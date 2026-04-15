# 交接文档 — 2026-04-15 会话结束

> 分支：master
> 最新 commit：`f8c18d5`（已在 Gitea，本地尚未提交）

## 本次会话完成的工作

### 1. 评分细则易用性改造 — 落地计划（文档）

制定了三条路线的完整落地计划，详见 `docs/评分细则易用性改造-落地计划.md`。

**核心结论**：
- 路线2（结构化卡片）→ 路线1（表单编辑）→ 路线3（自然语言描述）
- MVP 起点：英语编辑器第3步，用 subQuestions 直接渲染卡片
- 术语统一：UI 展示改为"评分细则"，代码内部变量名暂不变

### 2. 技术风险分析（已完成）

`loadChildren()` 从 DB 恢复 subQuestions 的数据完整性已确认。5 个风险点均有对策，详见落地计划文档"MVP 技术风险分析"章节。

### 3. 英语编辑器第3步改造（代码已写，已测试通过）

**已修改文件**（本地未提交）：

**`static/js/englishEditCore.js`**：
- 步骤标签 `评分脚本` → `评分细则`（line 21）
- 新增 `rubricViewMode = ref('cards')` 状态（line 57）
- 新增 `toggleRubricViewMode()` 方法（line 571 附近）
- `scriptCollapseActive` 默认改为空数组（原始脚本默认收起）
- return 中暴露 `rubricViewMode` 和 `toggleRubricViewMode`

**`templates/question-bank.html`** 第3步（520行起）：
- 标题改为"评分细则"，加"共 N 小问，满分 X 分"标签
- 新增卡片视图：按子题展开（el-collapse-item），每个子题显示：
  - 子题题目（灰色背景块）
  - 采分点列表：每个采分点显示 id + 分值 tag + 关键词（type="info"）+ 等价表述（type="success" plain）
  - 排除词（type="danger"）、拼音白名单（type="warning"）
  - hit_count 规则用 el-table 小表格
  - 无采分点时显示灰色提示"暂无采分点配置，请返回上一步添加"
- 原始脚本移到底部 el-collapse，标题灰色小字"原始脚本"，默认收起
- 自查/质量评估/生成功能按钮保留不变
- 导航按钮保留："← 返回修改采分点" + "确认脚本，进入验证 →"

## 下一步工作

### 立即执行
1. ~~启动服务测试第3步改造效果~~ — **已完成**（2026-04-15）
2. ~~测试要点：~~
   - ~~进入第3步看到卡片而非 textarea~~ ✅
   - ~~卡片正确展示采分点/关键词/等价表述~~ ✅
   - ~~原始脚本默认隐藏~~ ✅
   - ~~"共 N 小问，满分 X 分"标签~~ ✅
   - ~~无控制台关键错误~~ ✅
3. **提交推送修改**（未提交：englishEditCore.js + question-bank.html）

### 后续阶段
- 阶段2：新建 `rubricParser.js` 解析器，扩展到 dist/index.html、question-edit.html、rubric-workbench.html、question-view.html
- 阶段3：表单编辑（generateScript 逆向生成 + rubricCardEditor.js）
- 阶段4：自然语言输入（新 API + 提示词）

## UI 确认记录

| 元素 | 最终样式 | 和现有页面一致 |
|------|---------|--------------|
| 关键词 | el-tag type="info"，只读 | 是 |
| 等价表述 | el-tag type="success"，plain，只读 | 是 |
| 排除词 | el-tag type="danger"，只读 | 是 |
| 拼音白名单 | el-tag type="warning"，只读 | 是 |
| 原始脚本 | el-collapse 默认收起，底部灰色小字 | 同题目列表风格 |

## 其他 Agent 活动

Gitea 上有其他 Agent 推了新文件：
- `docs/api_routes拆分方案.md` — api_routes.py 拆分方案
- api_routes.py 已拆分完成（4316行→23行，11个路由文件+1共享模块）

新会话请先 `git pull gitea master` 再开始工作。
