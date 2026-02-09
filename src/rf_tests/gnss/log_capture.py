import re
import shlex
from pathlib import Path

from src.instruments.zepp_tool import ZeppTool
from src.utils.logger import get_logger

logger = get_logger()


class GNSSLogCapture:
    """
    数据采集器，操作 APP 导出 Terminal log 或者 NMEA log 到手机
    """
    TERM_PATTERN = re.compile(
        r'TERM-\d{4}\.\d{2}\.\d{2}-\d{2}\d{2}\d{2}\.log$'
    )
    NMEA_PATTERN = re.compile(
        r'NMEA-\d{4}\.\d{2}\.\d{2}-\d{2}\d{2}\d{2}\.txt$'
    )


    def __init__(
            self,
            zepp_tool: ZeppTool,
            local_log_dir: str | Path,
            device_log_dir: str | Path
    ):
        self._zt = zepp_tool
        self._local_log_dir = Path(local_log_dir)
        self._device_log_dir = Path(device_log_dir)

        self._local_log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"日志采集器初始化完成，本地目录: {self._local_log_dir}")

    def capture_term_log(
            self,
            term_repl: str = r"\g<0>",
            since_ts: int | None = None
    ) -> str | None:
        if not self._zt.export_term_log():
            logger.error("导出 Terminal 日志失败")
            return None

        return self._capture_log(
            pattern=self.TERM_PATTERN,
            pattern_type="terminal",
            repl=term_repl,
            since_ts=since_ts
        )

    def capture_nmea_log(
            self,
            nmea_repl: str = r"\g<0>",
            since_ts: int | None = None
    ) -> str | None:
        return self._capture_log(
            pattern=self.NMEA_PATTERN,
            pattern_type="nmea",
            repl=nmea_repl,
            since_ts=since_ts
        )

    def _capture_log(
            self,
            pattern: re.Pattern,
            pattern_type: str,
            repl: str,
            since_ts: int | None = None
    ) -> str | None:
        """

        :param pattern: 匹配原文件名的正则表达式
        :param pattern_type: 文件类型
        :param repl:
        :param since_ts: 单位为秒，如果 since_ts 为 None，则查找最新的 log 文件，否则查找 since_ts 之后的第一个 log 文件
        :return:
        """
        # 查找日志文件
        latest_log = self._find_latest_log(pattern=pattern, since_ts=since_ts)
        if not latest_log:
            logger.error(f"未找到 {pattern_type} 类型的日志文件")
            return None

        # 构建路径
        device_path = f"{self._device_log_dir}/{latest_log}"
        local_filename = pattern.sub(repl, latest_log)
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
            pattern: re.Pattern,
            since_ts: int | None = None
    ) -> str | None:
        """
        根据文件修改时间查找最新的文件
        :param pattern: 匹配文件名的正则表达式
        :param since_ts: 单位为秒，如果 since_ts 为 None，则查找最新的 log 文件，否则查找 since_ts 之后的第一个 log 文件
        :return:
        """
        output = self._zt.shell(f'ls -1 {self._device_log_dir}')
        files = output.splitlines() if output else []
        if not files:
            return None

        valid_logs = []
        for filename in files:
            match = pattern.match(filename)
            if not match:
                continue

            full_path = f"{self._device_log_dir}/{filename}"
            quoted = shlex.quote(full_path)
            out = self._zt.shell(f"stat -c %Y {quoted}").strip()
            if out.isdigit():
                mtime = int(out)
            else:
                continue

            valid_logs.append((mtime, filename))

        if not valid_logs:
            return None

        if since_ts is None:
            latest_log = max(valid_logs, key=lambda x: x[0])[1]
            return latest_log
        else:
            valid_logs.sort(key=lambda x: x[0])
            for ts, filename in valid_logs:
                if ts >= since_ts:
                    return filename
            return None

    @property
    def local_log_dir(self) -> Path:
        return self._local_log_dir
