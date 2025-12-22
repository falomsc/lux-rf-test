from abc import ABC, abstractmethod
from typing import Any


class BaseReporter(ABC):
    """报告生成器基类"""
    @abstractmethod
    def generate(self, data: list[dict[str, Any]], **kwargs) -> str:
        """生成报告，返回报告路径"""
        pass