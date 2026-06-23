"""
路由汇总模块
===========
将所有子路由统一导出，main.py 只需 import 一次即可完成全部注册。
新增路由时：在此文件 import + 加入 __all__ 列表。
"""

from app.api.routes.health import health_router
from app.api.routes.department import department_router
from app.api.routes.risk import risk_router
from app.api.routes.record import record_router
from app.api.routes.report import report_router
from app.api.routes.export import export_router
from app.api.routes.knowledge import knowledge_router

__all__ = [
    "health_router",
    "department_router",
    "risk_router",
    "record_router",
    "report_router",
    "export_router",
    "knowledge_router",
]
