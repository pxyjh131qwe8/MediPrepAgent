# FastApi 模块化路由机制


核心是ARIRouter
项目变大之后不再直接把路由写在main.py，APIRouter 是一个“小型 FastAPI 路由容器”，先在单独文件里收集接口，最后再统一挂载到主 app 上。