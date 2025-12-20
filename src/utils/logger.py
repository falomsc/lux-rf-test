import logging
import os
from datetime import datetime


def setup_logger(
    name: str = "rf_test",
    log_dir: str = "output/logs",
    level: int = logging.INFO
) -> logging.Logger:
    """设置日志器"""
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 文件handler
    log_filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(
        os.path.join(log_dir, log_filename),
        encoding="utf-8"
    )
    file_handler.setLevel(level)

    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # 格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "rf_test") -> logging.Logger:
    """获取已设置的日志器"""
    return logging.getLogger(name)