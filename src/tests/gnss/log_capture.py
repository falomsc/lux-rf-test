"""
GNSS 日志采集模块
负责从 Zepp Tool 采集并拉取日志文件
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.instruments.zepp_tool import ZeppTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GNSSLogCapture:
    """
    GNSS 日志采集器
    从 Zepp Tool 抓取日志并复制到 PC
    """

    # 日志文件名模式
    LOG_FILENAME_PATTERN = re.compile(
        r'^(?P<prefix>\w+)-'
        r'(?P<year>\d{4})\.(?P<month>\d{2})\.(?P<day>\d{2})-'
        r'(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})'
        r'\.log$'
    )

    def __init__(
        self,
        zepp_tool: ZeppTool,
        local_log_dir: str,
        device_log_dir: str
    ):
        """
        初始化日志采集器

        Args:
            zepp_tool: Zepp Tool 实例
            local_log_dir: 本地日志保存目录
            device_log_dir: 设备上的日志目录
        """
        self._zt = zepp_tool
        self._local_log_dir = Path(local_log_dir)
        self._device_log_dir = device_log_dir

        # 确保本地目录存在
        self._local_log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"日志采集器初始化完成，本地目录: {self._local_log_dir}")

    def capture_terminal_log(self, rename_prefix: str = "") -> Optional[str]:
        """
        导出并采集 Terminal 日志

        Args:
            rename_prefix: 文件重命名前缀

        Returns:
            本地日志文件路径，失败返回 None
        """
        # 先导出日志
        if not self._zt.export_terminal_log():
            logger.error("导出 Terminal 日志失败")
            return None

        return self._capture_log(prefix="TERM", rename_prefix=rename_prefix)

    def capture_nmea_log(self, rename_prefix: str = "") -> Optional[str]:
        """
        采集 NMEA 日志

        Args:
            rename_prefix: 文件重命名前缀

        Returns:
            本地日志文件路径，失败返回 None
        """
        return self._capture_log(prefix="NMEA", rename_prefix=rename_prefix)

    def _capture_log(
        self,
        prefix: str,
        rename_prefix: str = ""
    ) -> Optional[str]:
        """
        采集指定前缀的日志文件

        Args:
            prefix: 日志文件前缀（如 TERM、NMEA）
            rename_prefix: 文件重命名前缀

        Returns:
            本地日志文件路径，失败返回 None
        """
        # 查找最新的日志文件
        latest_log = self._find_latest_log(prefix)
        if not latest_log:
            logger.error(f"未找到 {prefix} 类型的日志文件")
            return None

        # 构建路径
        device_path = f"{self._device_log_dir}/{latest_log}"
        local_filename = f"{rename_prefix}{latest_log}"
        local_path = str(self._local_log_dir / local_filename)

        # 拉取文件
        if self._zt.pull_file(device_path, local_path):
            logger.info(f"成功采集日志: {latest_log} -> {local_path}")
            return local_path
        else:
            logger.error(f"采集日志失败: {latest_log}")
            return None

    def _find_latest_log(self, prefix: str) -> Optional[str]:
        """
        查找设备上最新的日志文件

        Args:
            prefix: 日志文件前缀

        Returns:
            最新日志文件名，未找到返回 None
        """
        files = self._zt.list_files(self._device_log_dir)
        if not files:
            return None

        latest_log = None
        latest_dt = None

        for filename in files:
            match = self.LOG_FILENAME_PATTERN.match(filename)
            if not match:
                continue

            if match.group('prefix') != prefix:
                continue

            # 解析日期时间
            try:
                dt = datetime(
                    int(match.group('year')),
                    int(match.group('month')),
                    int(match.group('day')),
                    int(match.group('hour')),
                    int(match.group('minute')),
                    int(match.group('second'))
                )
            except ValueError:
                continue

            if latest_dt is None or dt > latest_dt:
                latest_dt = dt
                latest_log = filename

        return latest_log

    @property
    def local_log_dir(self) -> Path:
        """获取本地日志目录"""
        return self._local_log_dir