"""
api_routes.py — API 路由入口

只保留 Blueprint 和评分引擎的定义（供 app.py 注册），
所有路由函数已拆分到 routes_xxx.py 子模块。

注意：api_bp 和 grading_engine 在 api_shared.py 中定义，
这里从 api_shared 重新导出，确保全局只有一个 Blueprint 对象。
"""
from app.api_shared import api_bp, grading_engine  # noqa: F401


# ─── 已拆分的子模块（导入触发路由注册）──────────────────────
from app import routes_admin  # noqa: F401, E402
from app import routes_auth  # noqa: F401, E402
from app import routes_questions  # noqa: F401, E402
from app import routes_english  # noqa: F401, E402
from app import routes_import  # noqa: F401, E402
from app import routes_dedup  # noqa: F401, E402
from app import routes_grading  # noqa: F401, E402
from app import routes_rubric  # noqa: F401, E402
from app import routes_ai  # noqa: F401, E402
from app import routes_testcases  # noqa: F401, E402
