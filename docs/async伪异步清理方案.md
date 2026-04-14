# async 伪异步清理方案

## 问题现状

Flask 3.0.2 + asgiref 3.11.1，9 个路由标了 `async def`，但核心评分函数 `QwenGradingEngine.grade()` 是同步阻塞的（用 `openai.OpenAI` 同步客户端 + `time.sleep` 重试），导致 `asyncio.gather` 并行失效。

### 调用链

```
Flask async 路由 (每个请求独立事件循环)
  └── three_layer_grade
        ├── [非英语] asyncio.gather(vector_task, run_llm)
        │     └── run_llm → grading_engine.grade ← 同步阻塞，事件循环被独占
        │                                            vector_task 被迫等待
        └── [英语] grade_english
              ├── grading_engine.grade ← 同步阻塞
              └── grade_english_fallback ← 同步阻塞
```

### 3 个伪异步函数

| 函数 | 文件:行 | 问题 |
|------|---------|------|
| `QwenGradingEngine.grade` | qwen_engine.py:106 | 同步 `OpenAI()` 客户端 + `time.sleep`，无 await |
| `grade_english_fallback` | english_grader.py:395 | 同步 `client.chat.completions.create()` + `time.sleep`，无 await |
| `generate_test_cases_for_question` | api_routes.py:3138 | 同步 `client.chat.completions.create()`，无 await |

### 6 个真异步路由（有 await，但依赖伪异步的 grade）

| 路由 | 文件:行 | 说明 |
|------|---------|------|
| `POST /api/grade` | api_routes.py:1472 | 核心评分 |
| `POST /api/batch` | api_routes.py:1978 | 批量评分 |
| `POST /api/verify-rubric` | api_routes.py:3484 | 验证脚本 |
| `POST /grading/single` | routes.py:25 | 旧评分入口 |
| `POST /api/batch/grade` | batch_routes.py:19 | 批量评分（旧） |
| `POST /api/batch/test` | batch_routes.py:77 | 性能测试（旧） |

### 3 个无需改动的路由

| 路由 | 文件:行 | 说明 |
|------|---------|------|
| `POST /validation/run` | validation_routes.py:16 | 调 `engine.aggregate`，真异步 |
| `POST /tuning/start` | tuning_routes.py:15 | 调 `AutoTuningEngine.tune`，真异步 |
| `POST /questions/.../generate-test-cases` | api_routes.py:3138 | 伪异步，但不阻塞评分链路 |

## 方案

### 核心思路：改 `grade()` 为同步函数

`QwenGradingEngine.grade()` 本身就是同步阻塞的（用 `openai.OpenAI` 同步客户端），强行标 `async` 没有意义，反而：
1. 欺骗调用方以为可以并行
2. Flask async 路由中阻塞事件循环

**直接去掉 `async`，改为普通 `def`。**

### 改动清单

#### 第 1 步：`QwenGradingEngine.grade` 去掉 async

**文件**: `app/qwen_engine.py:106`

```python
# 改前
async def grade(self, question, answer, rubric, max_score, subject="general", provider=None, model=None):

# 改后
def grade(self, question, answer, rubric, max_score, subject="general", provider=None, model=None):
```

影响：所有调用 `await grading_engine.grade(...)` 的地方需要去掉 `await`。

#### 第 2 步：`grade_english_fallback` 去掉 async

**文件**: `app/english_grader.py:395`

```python
# 改前
async def grade_english_fallback(...):

# 改后
def grade_english_fallback(...):
```

#### 第 3 步：`grade_english` 去掉 async

**文件**: `app/english_grader.py:591`

这个函数里 `await grading_engine.grade(...)` 和 `await grade_english_fallback(...)` 都改成同步调用后，自身也没有 await 了，也应去掉 async。

```python
# 改前
async def grade_english(answer, question_answers, max_score, grading_engine, question='', rubric=None):

# 改后
def grade_english(answer, question_answers, max_score, grading_engine, question='', rubric=None):
```

#### 第 4 步：`three_layer_grade` 适配

**文件**: `app/three_layer_grader.py:124`

当前写法：
```python
async def run_llm():
    return await grading_engine.grade(...)

keyword_result, vector_result, llm_result = await asyncio.gather(
    keyword_task, vector_task, run_llm()
)
```

改为同步后：
```python
def run_llm():
    return grading_engine.grade(...)

# 用线程池并行执行（同步函数需要在线程中跑）
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=3)

import asyncio
loop = asyncio.get_event_loop()
keyword_future = loop.run_in_executor(executor, lambda: keyword_match_score(...))
vector_future = loop.run_in_executor(executor, lambda: vector_match_score(...))
llm_future = loop.run_in_executor(executor, run_llm)

keyword_result, vector_result, llm_result = await asyncio.gather(
    keyword_future, vector_future, llm_future
)
```

**或者更简单的方案**：`three_layer_grade` 本身也改为同步函数。因为内部的 `keyword_match_score` 和 `vector_match_score` 本身就是同步的，只有 `grade_english` 和 `grading_engine.grade` 需要"异步"但实际是同步，所以整个调用链其实全是同步的。用 `concurrent.futures.ThreadPoolExecutor` 在路由层做并行。

#### 第 5 步：Flask 路由适配

当前 `grade_answer` 路由是 `async def`，里面 `await three_layer_grade(...)`。

两个选择：

**选择 A（推荐）：保留 async 路由，在路由内用 `loop.run_in_executor` 包装同步调用**

```python
@api_bp.route('/grade', methods=['POST'])
async def grade_answer():
    ...
    from concurrent.futures import ThreadPoolExecutor
    import asyncio
    loop = asyncio.get_event_loop()
    grade_result = await loop.run_in_executor(
        None,
        lambda: three_layer_grade(grading_engine=grading_engine, ...)
    )
```

**选择 B：三层评分也改为同步，路由全部改为普通 def**

这是最干净的做法。Flask 3.x 支持 async 路由但不是必须用。

```python
@api_bp.route('/grade', methods=['POST'])  # 去掉 async
def grade_answer():
    ...
    grade_result = three_layer_grade(grading_engine=grading_engine, ...)
```

但 `three_layer_grade` 内部想利用 `ThreadPoolExecutor` 做 keyword/vector/llm 三层并行，就需要一个事件循环。在同步路由中可以用：

```python
import asyncio
grade_result = asyncio.run(three_layer_grade(...))
```

**推荐选择 B**：所有路由和引擎函数统一改为同步，只在需要并行的地方用 `asyncio.run()` 包装。理由：
- 评分链路全是同步调用（同步 OpenAI 客户端），没有真正的异步 I/O
- Flask 的 async 路由对这种同步阻塞场景没有收益
- 代码更直观，不需要理解 async 语义

### 完整改动清单

| 文件 | 改动 | 影响 |
|------|------|------|
| `app/qwen_engine.py` | `grade()` 去掉 `async` | 4 个调用方去掉 `await` |
| `app/english_grader.py` | `grade_english_fallback()` 去掉 `async` | 1 个调用方去掉 `await` |
| `app/english_grader.py` | `grade_english()` 去掉 `async` | 1 个调用方去掉 `await` |
| `app/three_layer_grader.py` | `three_layer_grade()` 去掉 `async`，`asyncio.gather` 改为顺序执行或用 `ThreadPoolExecutor` | 1 个调用方去掉 `await` |
| `app/api_routes.py` | `grade_answer` 路由去掉 `async`，`await` 改为直接调用 | — |
| `app/api_routes.py` | `create_batch` 路由去掉 `async`，`await grading_engine.grade()` → 直接调用 | — |
| `app/api_routes.py` | `verify_rubric` 路由去掉 `async`，同上 | — |
| `app/api_routes.py` | `generate_test_cases_for_question` 路由去掉 `async`，同上 | — |
| `app/routes.py` | `grade_single` 路由去掉 `async` | — |
| `app/batch_routes.py` | `batch_grade` / `performance_test` 路由去掉 `async`（调用的是 engine.aggregate，需确认） | 需确认 engine.aggregate 是否真异步 |
| `app/tuning_routes.py` | `start_tuning` 路由去掉 `async`（调用 AutoTuningEngine.tune，需确认） | 需确认 |

### 三层并行方案

`three_layer_grade` 去掉 async 后，keyword/vector/llm 三层仍需并行。用 `ThreadPoolExecutor` 实现：

```python
from concurrent.futures import ThreadPoolExecutor

def three_layer_grade(grading_engine, question, answer, rubric, max_score,
                       subject, question_answers, strategy='avg',
                       provider=None, model=None):
    # 英语直接走独立模块
    if subject == 'english':
        return grade_english(...)

    # 非英语：三层并行
    with ThreadPoolExecutor(max_workers=3) as executor:
        keyword_future = executor.submit(keyword_match_score, answer, question_answers, max_score)
        vector_future = executor.submit(vector_match_score, answer, question_answers, max_score)
        llm_future = executor.submit(grading_engine.grade, question, answer, rubric, max_score, subject, provider, model)

        keyword_result = keyword_future.result()
        vector_result = vector_future.result()
        llm_result = llm_future.result()
    ...
```

这样同步函数也能真正并行，不需要事件循环。

### 需要确认的问题

1. `engine.aggregate`（routes.py / batch_routes.py / tuning_routes.py 中的旧引擎）是否还在用？如果已废弃，这些路由可以直接删除
2. `BaseModelClient` 体系（app/models/ 下的 5 个模型客户端）是否被 `QwenGradingEngine` 使用？如果完全没用，是另一处死代码

## 验证

1. 启动服务，单题评分正常返回结果
2. 批量评分多个题目并行执行，观察日志无 `database is locked`
3. 英语科目评分正常
4. `verify-rubric` 接口正常
