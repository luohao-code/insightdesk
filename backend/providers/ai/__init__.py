"""AI 引擎注册。"""

from ..registry import register_ai
from .mock import provider as mock_provider
from .openai_compatible import build_presets

register_ai(mock_provider)
for preset in build_presets():
    register_ai(preset)

__all__ = ["mock_provider", "build_presets"]
