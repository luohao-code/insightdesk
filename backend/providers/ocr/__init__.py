"""OCR 引擎注册。

导入本模块后，所有内置引擎自动完成注册。
新增引擎的步骤：
1. 新建模块并实现 :class:`OCRProvider`；
2. 在本文件导入并调用 ``register_ocr``；
3. 在前端设置页即可看到该引擎。
"""

from ..registry import register_ocr
from .baidu import provider as baidu_provider
from .mock import provider as mock_provider
from .rapidocr import provider as rapidocr_provider
from .tencent import provider as tencent_provider

register_ocr(mock_provider)
register_ocr(rapidocr_provider)
register_ocr(baidu_provider)
register_ocr(tencent_provider)

__all__ = ["mock_provider", "rapidocr_provider", "baidu_provider", "tencent_provider"]
