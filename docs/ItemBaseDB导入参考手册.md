# ItemBaseDB 导入参考手册

## 数据库基本信息

| 项目 | 值 |
|------|-----|
| 服务器 | 192.168.255.9 |
| 端口 | 1433（SQL Server 默认） |
| 数据库名 | ItemBaseDB |
| 登录账号 | sa |
| 密码 | Wuyou_2019 |
| 连接方式 | pyodbc，驱动 `{SQL Server}` |

```python
import pyodbc
conn = pyodbc.connect(
    'DRIVER={SQL Server};SERVER=192.168.255.9;DATABASE=ItemBaseDB;UID=sa;PWD=Wuyou_2019;',
    timeout=10
)
```

---

## 题目总量与科目分布

| 科目 | 题数 |
|------|------|
| 语文 | 3323 |
| 数学 | 2260 |
| 英语 | 1422 |
| 信息技术 | 1118 |
| 思品 | 286 |
| 历史 | 165 |
| **合计** | **8574** |

---

## 主要表结构

### Question（题目主表）

每道题对应一条记录，内容和答案存在关联表里。

| 字段 | 类型 | 含义 | 分析 |
|------|------|------|------|
| `oid` | GUID | 唯一标识 | 主键，用于关联所有子表 |
| `id` | int | 数字流水号 | 如 37793，可作为导入来源标记 |
| `uTitle` | GUID | 题目内容外键 | → QuestionTitle.oid |
| `uAnswer` | GUID | 答案外键 | → Answer.oid |
| `uQuestionType` | GUID | 题型外键 | → QuestionType.oid（注意：与实际题型可能不一致，见下） |
| `uBuiltQueType` | GUID | 实际题型 | 与 uQuestionType 值相同，以此为准 |
| `uDifficulty` | GUID | 难度外键 | → Difficulty.oid，值为 易/中/难 |
| `iSubjecttive` | int | 是否主观题 | 1=主观题，0=客观题 |
| `iState` | int | 状态 | 1=正常，其他值可能为删除/禁用 |
| `iExposalTimes` | int | 已使用次数 | 题目被组卷次数 |
| `iTotalCanBeTimes` | int | 最大可用次数 | 0=不限 |
| `iPurpose` | int | 用途标记 | 12道英语简答题全为2，含义待确认（推测：2=练习题） |
| `iDistinguish` | int | 区分度 | 0=未设置，值域推测 0-100 |
| `iRank` | int | 难度系数 | 本次样本全为空，可能未录入 |
| `dCreateTime` | datetime | 创建时间 | 2026-04-13 左右 |
| `dLastModifyTime` | datetime | 最后修改时间 | 可用于判断是否更新过 |
| `dLastUseTime` | datetime | 最后使用时间 | 全为空，未使用过 |
| `uCreateor` | GUID | 创建人 | → User.oid，样本中只有一个人 |
| `uModifier` | GUID | 最后修改人 | 同上 |
| `uCognize` | GUID | 认知层次 | 全为空，未录入 |
| `uSuit` | GUID | 套题关联 | 全为空，非套题 |
| `sAnalysor` | text | 解析人 | 全为空 |
| `sAnalyisis` | text | 解析内容 | **全为空**，无解析 |
| `DemoUrl` | text | 演示链接 | 全为空 |
| `bOperationType` | int | 操作类型 | 全为0，含义不明，忽略 |
| `iOrder` | int | 排序 | 全为空 |

---

### QuestionTitle（题目内容表）

| 字段 | 类型 | 含义 | 分析 |
|------|------|------|------|
| `oid` | GUID | 主键 | 被 Question.uTitle 引用 |
| `sContent` | text | 题目正文 | **XML 格式**，需解析（见下） |

`sContent` 格式示例：
```xml
<Topic>
  <Title><![CDATA[ HTML格式题目正文 ]]></Title>
  ...
</Topic>
```

提取方法：取 `<Title>...</Title>` 内的 CDATA，再去掉 HTML 标签。

---

### Answer（答案表）

| 字段 | 类型 | 含义 | 分析 |
|------|------|------|------|
| `oid` | GUID | 主键 | 被 Question.uAnswer 引用 |
| `sContent` | text | 答案+评分细则 | **XML + CDATA 格式**，含两部分内容（见下） |
| `sParser` | text | 解析补充 | 样本全为空 |

`sContent` 结构重点：

```
【标准答案】
  第1小题：...
  第2小题：...
  第3小题：...
【评分细则】
  第1小题：
    采分点1：关键词（条件描述）
    得分  条件
    2    命中得2分
  ...
```

**重要发现**：答案字段里除了标准答案，还内嵌了**采分点和评分细则**，包括：
- 每个采分点的关键词
- 得分条件（命中/部分命中）
- 每小题的分值

这意味着 `sContent` 实际上包含了我们系统所需的大部分评分信息，解析后可以直接用于生成评分脚本。

提取方法：
```python
import re

def parse_answer(raw):
    m = re.search(r'<keyContent>(.*?)</keyContent>', raw, re.DOTALL)
    text = m.group(1) if m else raw
    # 去 CDATA 和 HTML 标签
    text = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()

# 分离标准答案和评分细则
def split_answer(text):
    parts = re.split(r'【评分细则】|【评分说明】', text)
    standard = parts[0].strip()
    rubric = parts[1].strip() if len(parts) > 1 else ''
    return standard, rubric
```

---

### Difficulty（难度表）

| oid | sName | cSort |
|-----|-------|-------|
| BBE2FA2D-... | 易 | 1 |
| CAA2D72E-... | 中 | （未知） |
| 3FD74F79-... | 难 | （未知） |

映射到我们系统：易→easy，中→medium，难→hard

---

### QuestionType（题型表）

通过 `QuestionAndTypeRelation` 关联到题目。

英语相关题型：

| sName | oid |
|-------|-----|
| 英语[简答题] | 9084386A-206D-467B-A83B-C443C0E9CB43 |
| 英语[阅读理解] | CFD742E6-570C-4CB8-A35B-F82B431280D0 |
| 英语[单选题] | 16C846E7-2DF2-462B-ACC1-DC92C1AE6110 |

注意：QuestionAndTypeRelation 是多对多关系表（uQuestion → uQuestionType）。

---

### Subject（科目表）

| 字段 | 含义 |
|------|------|
| `oid` | 主键 |
| `sName` | 科目名（英语/语文/数学等） |
| `sCode` | 科目编码（多为空） |

通过 `SubjectQuestion`（uSubject → uQuestion）关联题目。

---

### Ken（知识点表）

| 字段 | 含义 |
|------|------|
| `oid` | 主键 |
| `sName` | 知识点名称 |
| `sCode` | 编码路径（如 `21808|21859`，代表知识点层级路径） |

通过 `QuestionKen`（uQuestion → uKen）关联题目。

注意：英语简答题的知识点全部标注为"英语简答题"，颗粒度较粗，导入时参考价值有限。

---

## 导入英语简答题的 SQL 查询

```sql
SELECT
    q.id            AS source_id,
    q.oid           AS source_oid,
    qt.sContent     AS title_xml,
    a.sContent      AS answer_xml,
    d.sName         AS difficulty,
    q.dCreateTime   AS created_at,
    q.dLastModifyTime AS updated_at,
    q.iExposalTimes AS use_count
FROM Question q
JOIN QuestionTitle qt        ON q.uTitle    = qt.oid
JOIN Answer a                ON q.uAnswer   = a.oid
JOIN Difficulty d            ON q.uDifficulty = d.oid
JOIN QuestionAndTypeRelation qr ON q.oid   = qr.uQuestion
WHERE qr.uQuestionType = '9084386A-206D-467B-A83B-C443C0E9CB43'
ORDER BY q.id
```

---

## 字段对应关系（源 → 目标）

| 源字段 | 目标字段 | 处理方式 |
|--------|----------|----------|
| title_xml（解析后前80字） | `title` | 截取正文标题段 |
| title_xml（解析后全文） | `content` | 去 XML/HTML 标签 |
| answer_xml（【标准答案】部分） | `standard_answer` | 分割提取 |
| answer_xml（【评分细则】部分） | `rubric_script` 备注 | 可辅助生成评分脚本 |
| difficulty（易/中/难） | `difficulty`（easy/medium/hard） | 映射转换 |
| 固定值 `english` | `subject` | 硬编码 |
| 固定值 `essay` | `question_type` | 硬编码 |
| 固定值 `6` | `max_score` | **源库无分值，暂定6分** |
| source_id / source_oid | `workflow_status` JSON | 存入来源标记 |
| created_at | `created_at` | 直接使用 |

---

## 缺失字段说明

| 目标字段 | 缺失原因 | 建议处理 |
|----------|----------|----------|
| `max_score` | 源库未存分值 | 默认6分，老师后续核对 |
| `rubric_script` | 源库无此概念 | 导入后用英语编辑器重新生成 |
| `rubric`（采分点JSON） | 格式不兼容 | 评分细则文字可辅助老师配置 |
| `title`（独立标题） | 源库无独立标题 | 截取正文第一行（居中标题段） |
| `parent_id` | 源库结构不同 | 暂不导入父子关系 |
