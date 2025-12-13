#!/usr/bin/env python3
"""
GNSS Desense 测试执行脚本
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tests.gnss.desense_test import GNSSDesenseTest
from src.reporters.gnss_reporter import GNSSReporter
from src.utils.config_loader import load_yaml_config
from src.utils.logger import setup_logger, get_logger


def main():
    parser = argparse.ArgumentParser(description='GNSS Desense 测试')
    parser.add_argument(
        '-c', '--config',
        default='config/test_cases/gnss_desense.yaml',
        help='测试配置文件路径'
    )
    parser.add_argument(
        '-o', '--output',
        default='output/reports/gnss_desense',
        help='报告输出目录'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细输出'
    )

    args = parser.parse_args()

    # 设置日志
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logger(level=log_level)
    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("GNSS Desense 测试")
    logger.info("=" * 60)

    try:
        # 加载配置
        config_path = project_root / args.config
        config = load_yaml_config(str(config_path))
        logger.info(f"已加载配置: {config_path}")

        # 创建测试实例
        test = GNSSDesenseTest(config)

        # 执行测试
        test.setup()
        try:
            results = test.run()
        finally:
            test.teardown()

        # 生成报告
        reporter = GNSSReporter(str(test.session_log_dir))
        log_formats = config.get('log_formats', ['json', 'xlsx'])
        report_files = reporter.generate(results, formats=log_formats)

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