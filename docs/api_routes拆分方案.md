# api_routes.py 拆分方案

> ~~当前行数：4316 行（含新增科目权限控制代码）~~
> **✅ 已完成** — api_routes.py 从 4316 行拆成 23 行入口 + 10 个路由文件 + 1 个共享模块
> 完成日期：2026-04-15
> 执行原则：**只搬代码，不改逻辑**，所有 URL 路径不变

---

## 一、总体思路

### 核心问题

`api_routes.py` 同时持有两个"全局对象"被各处使用：
- `api_bp` — Flask Blueprint，所有路由都注册在它上面
- `grading_engine` — 评分引擎实例，评分/AI生成类接口都要调用

如果直接拆分，各新文件都需要用这两个对象，就会产生**循环导入**。

### 解决方案：先建共享模块

新建 `app/api_shared.py`，把这两个对象和公共函数放进去。  
各新文件从 `api_shared.py` import，`api_routes.py` 也从它 import。  
这样依赖关系变成单向，不会循环。

### 拆分后的文件结构（✅ 已完成）

```
app/
├── api_shared.py          ← 共享对象（184行）
├── api_routes.py          ← 入口（23行，只导入子模块）
├── routes_auth.py         ← 登录/登出（36行）
├── routes_questions.py    ← 题目CRUD + 答案 + 评分参数 + 父子题（276行）
├── routes_english.py      ← 英语编辑器AI接口（124行）
├── routes_dedup.py        ← 去重/合并（327行）
├── routes_import.py       ← 导入/导出（556行）
├── routes_grading.py      ← 评分/历史/批量/统计/仪表盘（1025行）★ 最大
├── routes_rubric.py       ← 评分脚本生成/自查/验证/版本管理（517行）
├── routes_ai.py           ← 一致性检查/质量评估/自动出题（829行）
├── routes_testcases.py    ← 大纲/测试用例/生成测试用例（397行）
└── routes_admin.py        ← 敏感词/用户管理（135行）
```

---

## 二、第一步：新建 `app/api_shared.py`

这是最关键的一步，必须先做。

**内容：从 `api_routes.py` 剪切以下内容：**

| 内容 | 原文件行号 |
|------|-----------|
| 全部 import 语句 | 1–31 |
| `api_bp = Blueprint(...)` | 33 |
| `grading_engine = QwenGradingEngine(...)` | 34 |
| `PROVIDER_NAMES = {...}` | 83–91 |
| `_check_subject_access()` 函数 | 69–73 |
| `_session_subject()` 函数 | 76–80 |
| `_call_llm_sync()` 函数 | 429–451 |
| `_parse_json_from_llm()` 函数 | 454–470 |

**`api_shared.py` 文件结构：**

```python
"""
api_routes 共享对象 — Blueprint、评分引擎、公共辅助函数
所有 routes_xxx.py 从这里 import，避免循环依赖
"""
import json
import re
import time
from flask import Blueprint, request, jsonify, session
from loguru import logger
from app.models.db_models import (
    # 把原文件第7-27行的所有 import 完整复制过来
    ...
)
from app.qwen_engine import QwenGradingEngine
from app.models.registry import model_registry
from config.settings import GRADING_CONFIG

api_bp = Blueprint('api', __name__, url_prefix='/api')
grading_engine = QwenGradingEngine(GRADING_CONFIG)

PROVIDER_NAMES = { ... }  # 原文件83-91行

def _check_subject_access(target_subject):   # 原文件69-73行
    ...

def _session_subject():                       # 原文件76-80行
    ...

def _call_llm_sync(system_prompt, user_prompt):   # 原文件429-451行
    ...

def _parse_json_from_llm(raw):                    # 原文件454-470行
    ...
```

---

## 三、各新文件说明

### 3.1 `routes_auth.py`（~45行）

**剪切原文件行：** 37–66（login、logout 两个路由）

**文件头：**
```python
from flask import request, jsonify, session
from app.api_shared import api_bp
from app.models.db_models import get_user
```

**包含路由：**
- `POST /api/login`
- `POST /api/logout`

---

### 3.2 `routes_questions.py`（~420行）

**剪切原文件行：** 286–708（题目CRUD + 英语编辑器之外的部分 + 答案管理 + 评分参数 + 父子题）

具体包含：
- 286–302：`GET /api/questions`
- 303–328：`GET /api/questions/<id>`
- 329–364：`POST /api/questions`
- 365–404：`PUT /api/questions/<id>`
- 405–426：`PUT /api/questions/<id>/workflow-status`
- 590–603：`DELETE /api/questions/<id>`
- 604–683：满分答案 CRUD（`/answers`）
- 664–708：评分参数 + 父子题查询

**注意：** 英语编辑器路由（427–589）单独放 `routes_english.py`，不放这里。

**文件头：**
```python
import json
from flask import request, jsonify
from app.api_shared import api_bp, _check_subject_access, _session_subject
from app.models.db_models import (
    add_question, get_questions, get_question,
    update_question, delete_question,
    get_question_answers, add_question_answer,
    update_question_answer, delete_question_answer,
    get_grading_param, get_all_grading_params, set_grading_param,
    get_child_questions, get_question_with_children,
)
from loguru import logger
```

---

### 3.3 `routes_english.py`（~170行）

**剪切原文件行：** 427–589（英语编辑器AI接口，不含辅助函数——辅助函数已移到 api_shared）

包含路由：
- `POST /api/english/extract`
- `POST /api/english/extract-scoring-points`
- `POST /api/english/suggest-synonyms`
- `POST /api/english/suggest-exclude`
- `POST /api/english/generate-rubric`

**文件头：**
```python
from flask import request, jsonify
from app.api_shared import api_bp, _call_llm_sync, _parse_json_from_llm, _check_subject_access
from app.english_prompts import (
    # 英语编辑器相关的 prompts（按需 import，不用全部导入）
)
from loguru import logger
```

---

### 3.4 `routes_dedup.py`（~325行）

**剪切原文件行：** 709–1030（去重、合并、查重）

包含：
- 709–826：`POST /api/questions/find-duplicates`
- 827–909：`_build_merge_suggestion()` 辅助函数
- 910–967：`POST /api/questions/merge`
- 968–1030：`POST /api/questions/find-same-number`

**文件头：**
```python
import json
from flask import request, jsonify
from app.api_shared import api_bp, _check_subject_access
from app.models.db_models import get_questions, get_question, update_question, delete_question
from loguru import logger
```

---

### 3.5 `routes_import.py`（~555行）

**剪切原文件行：** 1031–1581（导出评分脚本 + 导入题目 + 导入Word）

包含路由：
- `GET  /api/export-rubric-scripts`
- `POST /api/import-questions/preview`
- `POST /api/import-questions`
- `POST /api/import-word`
- `POST /api/import-word/confirm`

**文件头：**
```python
import json
from flask import request, jsonify
from app.api_shared import api_bp, _check_subject_access
from app.models.db_models import get_questions, get_question, add_question, update_question
from loguru import logger
```

---

### 3.6 `routes_grading.py`（~970行）

**剪切原文件行：** 1582–2547（评分核心 + 历史 + 批量 + 统计 + 仪表盘）

包含路由：
- `POST /api/grade`（最大的函数，约500行）
- `GET  /api/history`
- `POST /api/batch`
- `GET  /api/batch/<id>`
- `GET  /api/stats`
- `GET  /api/dashboard`

**文件头：**
```python
import json
import asyncio
from flask import request, jsonify, session
from app.api_shared import api_bp, grading_engine, _check_subject_access, _session_subject
from app.models.db_models import (
    get_question, add_grading_record, get_grading_history,
    create_batch_task, update_batch_task, get_batch_task,
    get_questions, check_sensitive_words, get_previous_grade,
    get_child_questions, get_question_with_children,
    save_script_version,
)
from app.english_prompts import is_empty_answer_en, is_short_answer_en
from loguru import logger
```

> ⚠️ 注意：原文件在 `grade_answer()` 前有一行 `import asyncio`（行内 import），  
> 移到这个文件时改为文件顶部 import。

---

### 3.7 `routes_rubric.py`（~500行）

**剪切原文件行：** 2548–2822 + 3782–3919（评分脚本生成/自查/验证）

包含路由：
- `GET  /api/models/available`
- `POST /api/generate-rubric-points`
- `POST /api/generate-rubric-script`
- `POST /api/self-check-rubric`
- `POST /api/verify-rubric`

**同时剪切：** 原文件 132–230 的两个大 Prompt 常量：
- `RUBRIC_SCRIPT_SYSTEM_PROMPT`（132–164行）→ 移到本文件顶部
- `SELF_CHECK_RUBRIC_SYSTEM_PROMPT`（如有）→ 也移到本文件

**文件头：**
```python
import json
import asyncio
from flask import request, jsonify
from app.api_shared import api_bp, grading_engine, _call_llm_sync, _check_subject_access
from app.models.db_models import (
    get_question, get_test_cases, save_script_version,
    update_script_version_result,
)
from app.models.registry import model_registry
from app.english_prompts import (
    RUBRIC_SCRIPT_SYSTEM_PROMPT_EN,
    SELF_CHECK_RUBRIC_SYSTEM_PROMPT_EN,
    make_rubric_points_prompt_en,
    make_rubric_script_prompt_en,
    make_self_check_prompt_en,
)
from loguru import logger

RUBRIC_SCRIPT_SYSTEM_PROMPT = """..."""   # 从原文件132-164行剪切
```

---

### 3.8 `routes_ai.py`（~700行）

**剪切原文件行：** 2823–3260 + 3638–3715 + 3920–4195（命题评估/一致性/自动出题/生成答案）

包含路由：
- `GET  /api/bugs`
- `POST /api/check-consistency`
- `POST /api/batch-check-consistency`
- `POST /api/evaluate-question`
- `POST /api/generate-answer`
- `POST /api/auto-generate`

**同时剪切：**
- `QUALITY_EVALUATION_SYSTEM_PROMPT`（原文件187–235行）→ 移到本文件顶部
- `AUTO_GEN_QUESTION_SYSTEM` prompt（原文件3920附近）→ 已在该区段内

**文件头：**
```python
import json
import asyncio
from flask import request, jsonify
from app.api_shared import api_bp, grading_engine, _call_llm_sync, _check_subject_access
from app.models.db_models import (
    get_question, get_grading_history, log_bug,
    add_question, add_test_case, save_script_version,
)
from app.english_prompts import (
    QUALITY_EVALUATION_SYSTEM_PROMPT_EN,
    AUTO_GEN_QUESTION_SYSTEM_EN,
    AUTO_GEN_TESTCASE_SYSTEM_EN,
    STYLE_GUIDE_EN,
    make_evaluate_question_prompt_en,
    make_auto_gen_question_prompt_en,
    make_auto_gen_rubric_prompt_en,
    make_auto_gen_testcase_prompt_en,
    make_evaluate_fallback_en,
)
from loguru import logger

QUALITY_EVALUATION_SYSTEM_PROMPT = """..."""  # 从原文件187-235行剪切
```

---

### 3.9 `routes_testcases.py`（~460行）

**剪切原文件行：** 3261–3637 + 3716–3781（大纲 + 测试用例 + 脚本历史）

包含路由：
- `GET/POST/DELETE /api/syllabus`
- `GET  /api/test-cases/overview`
- `GET  /api/test-cases/all`
- `GET/POST /api/questions/<id>/test-cases`
- `PUT/DELETE /api/questions/<id>/test-cases/<tid>`
- `POST /api/questions/<id>/generate-test-cases`
- `GET  /api/questions/<id>/script-history`
- `POST /api/questions/<id>/script-rollback`

**文件头：**
```python
import json
import asyncio
from flask import request, jsonify
from app.api_shared import api_bp, grading_engine, _call_llm_sync, _check_subject_access
from app.models.db_models import (
    get_syllabus, get_all_syllabus, upsert_syllabus, delete_syllabus,
    add_test_case, get_test_cases, get_test_case,
    update_test_case, delete_test_case, update_test_case_result,
    get_all_test_cases_overview, get_all_test_cases_with_question,
    get_script_history, get_script_version, save_script_version,
    get_question,
)
from app.english_prompts import (
    AUTO_GEN_TESTCASE_SYSTEM_EN,
    make_auto_gen_testcase_prompt_en,
)
from loguru import logger
```

---

### 3.10 `routes_admin.py`（~120行）

**剪切原文件行：** 4196–4316（敏感词管理 + 用户管理）

包含路由：
- `GET/POST/PUT/DELETE /api/sensitive-words`
- `POST /api/sensitive-words/batch`
- `GET/POST/PUT/DELETE /api/users`

**文件头：**
```python
from flask import request, jsonify
from app.api_shared import api_bp
from app.models.db_models import (
    get_sensitive_words, add_sensitive_word, update_sensitive_word,
    delete_sensitive_word, batch_add_sensitive_words,
    get_users, get_user, add_user as db_add_user, update_user, delete_user,
)
from loguru import logger
```

---

## 四、最终的 `api_routes.py`（保留约60行）

拆完之后，原文件只保留：

```python
"""
API 路由入口 — 定义 Blueprint，导入所有子模块以注册路由
"""
from app.api_shared import api_bp, grading_engine, PROVIDER_NAMES  # noqa: F401

# 导入各子模块，触发路由注册（顺序不影响功能）
from app import routes_auth          # noqa: F401
from app import routes_questions     # noqa: F401
from app import routes_english       # noqa: F401
from app import routes_dedup         # noqa: F401
from app import routes_import        # noqa: F401
from app import routes_grading       # noqa: F401
from app import routes_rubric        # noqa: F401
from app import routes_ai            # noqa: F401
from app import routes_testcases     # noqa: F401
from app import routes_admin         # noqa: F401

# /providers 接口保留在这里（依赖 grading_engine + PROVIDER_NAMES）
from flask import request, jsonify
from app.models.db_models import get_effective_config

@api_bp.route('/providers', methods=['GET'])
def list_enabled_providers():
    # ... 原文件94-131行，完整复制
```

> `app.py` **不需要修改**。它仍然 `from .api_routes import api_bp`，这条语句会触发
> 上面所有 import，所有路由都会被注册。

---

## 五、执行顺序建议

按从简单到复杂的顺序，每步完成后运行 `python main.py` 验证无报错：

| 步骤 | 操作 | 风险 |
|------|------|------|
| 1 | 新建 `api_shared.py`，从原文件剪切共享内容 | 低 |
| 2 | 新建 `routes_admin.py`（最简单，无复杂依赖） | 低 |
| 3 | 新建 `routes_auth.py` | 低 |
| 4 | 新建 `routes_questions.py` | 低 |
| 5 | 新建 `routes_english.py` | 低 |
| 6 | 新建 `routes_dedup.py` | 低 |
| 7 | 新建 `routes_import.py` | 中 |
| 8 | 新建 `routes_testcases.py` | 中 |
| 9 | 新建 `routes_rubric.py`（含Prompt常量迁移） | 中 |
| 10 | 新建 `routes_ai.py`（含Prompt常量迁移） | 中 |
| 11 | 新建 `routes_grading.py`（最复杂，grade函数500行） | 高 |
| 12 | 清理 `api_routes.py`，只保留入口代码 | 高 |

---

## 六、验证方法

每拆一个文件后执行：

```bash
# 1. 启动不报错
python main.py

# 2. 测试对应接口（举例）
curl http://localhost:5001/api/questions
curl http://localhost:5001/api/providers

# 3. 用 Playwright 跑回归（如有）
npx playwright test
```

---

## 七、注意事项

1. **`import asyncio` 问题**：原文件第1579行有一个行内 `import asyncio`，放在 `grade_answer()` 函数前。拆分到 `routes_grading.py` 时改为文件顶部 import。

2. **Prompt 常量位置**：
   - `RUBRIC_SCRIPT_SYSTEM_PROMPT` → `routes_rubric.py` 顶部
   - `QUALITY_EVALUATION_SYSTEM_PROMPT` → `routes_ai.py` 顶部  
   - `AUTO_GEN_QUESTION_SYSTEM` → `routes_ai.py`（已在该区段内）
   - 原文件132–285行的这两块内容，拆完后从 `api_routes.py` 删掉

3. **english_prompts 分散 import**：同一个 `english_prompts.py` 里的函数被多个新文件用到，每个文件按需 import 自己用到的部分即可。

4. **循环导入检查**：所有新文件只从 `api_shared.py` import，`api_shared.py` 不 import 任何 `routes_xxx.py`，没有循环依赖。

5. **`_build_merge_suggestion()`**：这是 `routes_dedup.py` 的内部辅助函数，不需要对外暴露，直接放在该文件里即可。

6. **`routes_import.py` 的 db import 需自行补全**：文档中只列出了常用的4个 db 函数作为示例，实际上导出评分脚本、导入Word等功能还用到更多函数。执行 Agent 应在搬代码时，检查每个函数用到了哪些 db 操作，逐一补进 import，不能只照搬文档示例。

7. **import 漏写的表现**：如果某个新文件漏写了某个 import，`python main.py` 启动时会立刻抛出 `ImportError` 或 `NameError`，不会悄悄运行出错。报错信息会直接显示缺少哪个名称，按提示补上即可。**不存在"运行正常但功能出错"的情况**，排查非常容易。

---

## 八、完成总结（2026-04-15）

### 最终成果

| 指标 | 拆分前 | 拆分后 |
|------|--------|--------|
| `api_routes.py` 行数 | 4316 | **23**（-99.5%） |
| 文件数 | 1 | **12**（1入口 + 10路由 + 1共享） |
| API 路由数 | 77 | **79**（无丢失，新增2个是此前遗漏的路由） |
| 启动状态 | 正常 | **正常，无报错** |

### 执行分 4 轮完成

1. **第一轮**（前次会话）：api_shared + routes_admin + routes_auth + routes_questions + routes_english + routes_dedup + routes_import（6/12 完成）
2. **第二轮**（本次会话）：routes_grading + routes_rubric + routes_ai + routes_testcases + api_routes 清理（完成剩余 6/12）
3. **统一改造**：所有子模块 `from app.api_routes import api_bp` → `from app.api_shared import api_bp`
4. **验证**：启动无报错 + 79 路由全部注册 + 39 个关键路由逐一确认

### 关键设计决策

- **Blueprint 单一来源**：`api_bp` 只在 `api_shared.py` 中定义，`api_routes.py` 从 `api_shared` 重新导出。子模块统一从 `api_shared` 导入。避免了多个 Blueprint 对象的混乱。
- **Prompt 常量归属**：`RUBRIC_SCRIPT_SYSTEM_PROMPT` 放在 `api_shared.py`（被 routes_rubric 和 routes_ai 共同引用）；`QUALITY_EVALUATION_SYSTEM_PROMPT`、`AUTO_GEN_*` 放在 `routes_ai.py`（只有该文件用到）。
- **`import asyncio` 清理**：原文件行内 import 已移至文件顶部。
