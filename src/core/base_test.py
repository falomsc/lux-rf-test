from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass, field

from src.reporters.base_reporter import BaseReporter


@dataclass
class TestResult:
    """测试结果数据类"""
    test_name: str
    passed: bool
    data: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


class BaseTest(ABC):
    """所有测试的基类"""
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.results: list[dict] = []
        self.reporter: BaseReporter | None = None
        self._test_name = config.get("test_name", self.__class__.__name__)

    @property
    def test_name(self) -> str:
        return self._test_name

    def set_reporter(self, reporter: BaseReporter) -> None:
        """设置报告生成器"""
        self.reporter = reporter

    @abstractmethod
    def setup(self) -> None:
        """测试准备 - 子类实现"""
        pass

    @abstractmethod
    def execute(self) -> None:
        """执行测试 - 子类实现"""
        pass

    @abstractmethod
    def teardown(self) -> None:
        """测试清理 - 子类实现"""
        pass

    def run(self) -> TestResult:
        """运行完整测试流程"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.test_name}")
        print(f"{'='*60}\n")

        errors = []
        try:
            self.setup()
            self.execute()
        except Exception as e:
            errors.append(str(e))
            print(f"测试执行出错: {e}")
            raise
        finally:
            self.teardown()

        # 生成报告
        if self.reporter and self.results:
            self.reporter.generate(self.results)

        # 汇总结果
        overall_pass = all(r.get("pass_fail", False) for r in self.results)
        return TestResult(
            test_name=self.test_name,
            passed=overall_pass,
            data=self.results,
            errors=errors
        )