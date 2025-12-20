import os
from typing import Any

import yaml

from src.core.exceptions import ConfigError


def load_config(filepath: str) -> dict[str, Any]:
    """
    读取 YAML 配置
    :param filepath:
    :return:
    """
    if not os.path.exists(filepath):
        raise ConfigError(f"配置文件不存在: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
            return config if config else {}
        except yaml.YAMLError as e:
            raise ConfigError(f"配置文件解析错误: {e}")


def merge_configs(*configs: dict) -> dict:
    """合并多个配置字典"""
    result = {}
    for config in configs:
        result.update(config)
    return result