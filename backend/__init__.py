"""识文台 InsightDesk 后端包。

本包采用分层架构：
- ``api``        HTTP 接口层，只负责参数校验与响应封装
- ``services``   业务服务层，编排领域逻辑
- ``providers``  外部能力适配层（OCR / 大模型）
- ``models``     数据持久化层（SQLAlchemy ORM）
- ``schemas``    数据传输对象（Pydantic）
- ``utils``      通用工具
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
