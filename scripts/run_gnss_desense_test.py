import shutil
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rf_tests.gnss.desense_test import GNSSDesenseTest
from src.reporters.gnss_reporter import GNSSReporter
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, get_logger

CONFIG_RELATIVE_PATH = Path('config/test_cases/gnss_desense.yaml')
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_LEVEL = 'INFO'


def main():
    setup_logger(level=LOG_LEVEL)
    logger = get_logger(__name__)
    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("GNSS Desense 测试")
    logger.info("=" * 60)
    logger.info(f"报告输出目录: {REPORT_OUTPUT_DIR}")

    try:
        config_path = project_root / CONFIG_RELATIVE_PATH
        config = load_config(str(config_path))
        logger.info(f"已加载配置: {config_path}")

        test = GNSSDesenseTest(config)
        test.setup()
        try:
            results = test.run()
        finally:
            test.teardown()

        reporter = GNSSReporter(str(test.session_log_dir))
        log_formats = config.get('log_formats', ['json', 'xlsx', 'dashboard'])
        report_files = reporter.generate(results, formats=log_formats)
        copied_report_files = []
        for report_path in report_files:
            src = Path(report_path)
            dst = REPORT_OUTPUT_DIR / src.name
            shutil.copy2(src, dst)
            copied_report_files.append(dst)


        logger.info("=" * 60)
        logger.info("测试完成！")
        logger.info(f"日志目录: {test.session_log_dir}")
        for f in report_files:
            logger.info(f"报告文件: {f}")
        logger.info("=" * 60)
        return 0

    except FileNotFoundError as e:
        logger.error(f"配置文件不存在: {e}")
        return 1
    except Exception as e:
        logger.exception(f"测试执行失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
