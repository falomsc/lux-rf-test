import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

from src.instruments.zepp_tool import ZeppTool
from src.utils.logger import get_logger

logger = get_logger()


class GNSSLogCapture:
    """
    数据采集器，可以采集 Terminal log 或者 NMEA log
    """
    LOG_FILENAME_PATTERNS = {
        "terminal": re.compile(
            r'TERM-'
            r'(?P<year>\d{4})\.(?P<month>\d{2})\.(?P<day>\d{2})-'
            r'(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})'
            r'\.log$'
        ),
        "nmea": re.compile(
            r'NMEA-'
            r'(?P<year>\d{4})\.(?P<month>\d{2})\.(?P<day>\d{2})-'
            r'(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})'
            r'\.txt$'
        )
    }

    def __init__(
            self,
            zepp_tool: ZeppTool,
            local_log_dir: str | Path,
            device_log_dir: str | Path
    ):
        self._zt = zepp_tool
        self._local_log_dir = Path(local_log_dir)
        self._device_log_dir = device_log_dir

        self._local_log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"日志采集器初始化完成，本地目录: {self._local_log_dir}")

    def capture_terminal_log(
            self,
            rename_prefix: str = "",
            start_time: Optional[datetime] = None
    ) -> Optional[str]:
        """

        :param rename_prefix:
        :param start_time: 如果 start_time 为 None，则查找最新的 log 文件，否则查找 start_time 之后的第一个 log 文件
        :return:
        """
        if not self._zt.export_terminal_log():
            logger.error("导出 Terminal 日志失败")
            return None

        return self._capture_log(
            pattern_type="terminal",
            rename_prefix=rename_prefix,
            start_time=start_time
        )

    def capture_nmea_log(
            self,
            rename_prefix: str = "",
            start_time: Optional[datetime] = None
    ) -> Optional[str]:
        return self._capture_log(
            pattern_type="nmea",
            rename_prefix=rename_prefix,
            start_time=start_time
        )

    # TODO 使用正则表达式匹配
    def _capture_log(
            self,
            pattern_type: Literal["terminal", "nmea"],
            rename_prefix: str = "",
            start_time: Optional[datetime] = None
    ) -> Optional[str]:
        """

        :param pattern_type:
        :param rename_prefix: 原始文件名字的基础上增加前缀，比如 rename_prefix = "positioning-1-"，
        原始文件为TERM-2025.11.15-163254.log，则导出的文件为 positioning-1-TERM-2025.11.15-163254.log
        :param start_time: 如果 start_time 为 None，则查找最新的 log 文件，否则查找 start_time 之后的第一个 log 文件
        :return:
        """
        # 查找日志文件
        latest_log = self._find_latest_log(pattern_type=pattern_type, start_time=start_time)
        if not latest_log:
            logger.error(f"未找到 {pattern_type} 类型的日志文件")
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

    def _find_latest_log(
            self,
            pattern_type: Literal["terminal", "nmea"],
            start_time: Optional[datetime] = None
    ) -> Optional[str]:
        """

        :param pattern_type: 匹配文件类型，terminal 或 nmea
        :param start_time: 如果 start_time 为 None，则查找最新的 log 文件，否则查找 start_time 之后的第一个 log 文件
        :return:
        """
        files = self._zt.list_device_files(self._device_log_dir)
        if not files:
            return None

        valid_logs = []
        for filename in files:
            match = self.LOG_FILENAME_PATTERNS[pattern_type].match(filename)
            if not match:
                continue
            try:
                dt = datetime(
                    int(match.group('year')),
                    int(match.group('month')),
                    int(match.group('day')),
                    int(match.group('hour')),
                    int(match.group('minute')),
                    int(match.group('second'))
                )
                valid_logs.append((dt, filename))
            except ValueError:
                continue

        if not valid_logs:
            return None

        if start_time is None:
            latest_log = max(valid_logs, key=lambda x: x[0])[1]
            return latest_log
        else:
            valid_logs.sort(key=lambda x: x[0])
            for dt, filename in valid_logs:
                if dt >= start_time:
                    return filename
            return None

    @property
    def local_log_dir(self) -> Path:
        return self._local_log_dir
