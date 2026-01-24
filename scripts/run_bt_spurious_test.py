import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rf_tests.bluetooth.spurious_test import BluetoothSpuriousTest
from src.reporters.excel_reporter import ExcelReporter
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger


def main():
    # 设置日志
    logger = setup_logger("bt_spurious")
    logger.info("开始蓝牙杂散测试")

    try:
        # 加载配置
        instruments_config = load_config("config/instruments.yaml")
        test_config = load_config("config/test_cases/bluetooth_spurious.yaml")

        # 创建测试实例
        test = BluetoothSpuriousTest(
            config=test_config,
            instrument_config=instruments_config
        )

        # 设置报告生成器
        reporter = ExcelReporter(output_dir="output/reports")
        test.set_reporter(reporter)

        # 运行测试
        result = test.run()

        # 打印结果
        if result.passed:
            logger.info("测试通过!")
        else:
            logger.warning("测试失败!")

        return 0 if result.passed else 1

    except Exception as e:
        logger.error(f"测试异常: {e}", exc_info=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())