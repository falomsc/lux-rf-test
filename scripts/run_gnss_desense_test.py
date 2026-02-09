import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rf_tests.gnss.desense_test import GNSSDesenseTest
from src.reporters.gnss_reporter import GNSSReporter
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, get_logger

CONFIG_PATH = project_root / "config" / "test_cases" / "gnss_desense.yaml"
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_DIR = project_root / "output" / "logs"
REPORT_OUTPUT_DIR = project_root / "output" / "gnss desense" / TIMESTAMP
LOG_LEVEL = 'INFO'


def main():
    setup_logger(level=LOG_LEVEL, log_dir=LOG_DIR)
    logger = get_logger(__name__)
    (project_root / REPORT_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("GNSS Desense 测试")
    logger.info("=" * 60)
    logger.info(f"报告输出目录: {REPORT_OUTPUT_DIR}")

    try:
        config = load_config(str(CONFIG_PATH))
        logger.info(f"已加载配置: {CONFIG_PATH}")

        test = GNSSDesenseTest(config)
        test.setup()
        try:
            gnss_results = test.run()
        finally:
            test.teardown()

        reporter = GNSSReporter(str(test.session_log_dir))
        log_config = config.get('log_config', {})
        log_formats = log_config.get('log_formats', ['json', 'xlsx', 'dashboard'])
        json_filename = log_config.get('json_filename', 'gnss_desense_result.json')
        xlsx_filename = log_config.get('xlsx_filename', 'gnss_desense_result.xlsx')
        dashboard_filename = log_config.get('dashboard_filename', 'gnss_desense_result.html')
        report_files = reporter.generate(gnss_results, formats=log_formats,
                                         json_filename=json_filename,
                                         excel_filename=xlsx_filename,
                                         dashboard_filename=dashboard_filename)
        logger.info("=" * 60)
        logger.info("测试完成！")
        logger.info(f"日志目录: {test.session_log_dir}")
        for f in report_files:
            logger.info(f"报告文件: {f}")
        logger.info("=" * 60)
        if reporter.app is not None and log_config.get('dashboard_auto_open'):
            u = urlparse(log_config.get('dashboard_address'))
            host = u.hostname
            port = u.port
            reporter.app.run(debug=True, host=host, port=port)

    except FileNotFoundError as e:
        logger.error(f"配置文件不存在: {e}")
        return 1
    except Exception as e:
        logger.exception(f"测试执行失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
