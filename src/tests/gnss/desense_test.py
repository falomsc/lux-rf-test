import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.base_test import BaseTest
from src.instruments.zepp_tool import ZeppTool
from src.tests.gnss.log_capture import GNSSLogCapture
from src.tests.gnss.log_parser import (
    parse_terminal_gnss_log,
    parse_nmea_log,
    convert_nmea_to_gnss_info,
    AllowedMode
)
from src.utils.logger import get_logger
from src.utils.time_utils import format_duration

logger = get_logger()


@dataclass
class DesenseTestCase:
    name: str
    description: str = ""
    start_cmd: list[str] = field(default_factory=list)
    end_cmd: list[str] = field(default_factory=list)
    start_delay: int = 0
    need_reboot: bool = False
    duration: int = 30
    log_prefix: str = ""
    enabled: bool = True

    @classmethod
    def from_dict(cls, name: str, data: dict) -> 'DesenseTestCase':
        start_cmd = data.get('start_cmd', '')
        if isinstance(start_cmd, str):
            start_cmd = [start_cmd] if start_cmd else []
        elif not isinstance(start_cmd, list):
            start_cmd = []

        end_cmd = data.get('end_cmd', '')
        if isinstance(end_cmd, str):
            end_cmd = [end_cmd] if end_cmd else []
        elif not isinstance(end_cmd, list):
            end_cmd = []

        return cls(
            name=name,
            description=data.get('description', ''),
            start_cmd=start_cmd,
            end_cmd=end_cmd,
            start_delay=data.get('start_delay', 0),
            need_reboot=data.get('need_reboot', False),
            duration=data.get('duration', 30),
            log_prefix=data.get('log_prefix', name),
            enabled=data.get('enabled', True)
        )


@dataclass
class DesenseTestResult:
    """Desense 测试结果"""
    case_name: str
    gnss_infos: list[dict]
    start_time: datetime
    end_time: datetime
    success: bool
    error_message: str = ""


class GNSSDesenseTest(BaseTest):
    def __init__(self, config: dict):
        super().__init__(config)

        # 设备配置
        device_cfg = config.get('device', {})
        self.device_id = device_cfg.get('device_id', '')
        self.device_log_dir = device_cfg.get('zt_log_dir', '/sdcard/hmbletool/')
        self.local_log_dir = device_cfg.get('local_log_dir', './output/logs/gnss_desense')

        # 测试参数
        test_params = config.get('test_params', {})
        self.pos_scan_interval = test_params.get('pos_scan_interval', 30)
        self.reboot_time = test_params.get('reboot_time', 60)
        self.default_duration = test_params.get('default_duration', 30)  # TODO 此参数是否可以删除

        # GNSS 配置
        self.pos_cmd = config.get('pos_cmd', [])
        self.reboot_cmd = config.get('reboot_cmd', 'hm:sft+power=reboot')
        gnss_modes = config.get('gnss_modes', ['gps', 'bds', 'gal', 'gln'])
        self.gnss_modes: tuple[AllowedMode, ...] = tuple(gnss_modes)

        # 日志格式
        self.log_formats = config.get('log_formats', ['json', 'xlsx'])

        # 加载测试用例
        self.test_cases: list[DesenseTestCase] = []
        for name, case_config in config.get('testing_cases', {}).items():
            case = DesenseTestCase.from_dict(name, case_config)
            if case.enabled:
                self.test_cases.append(case)

        # 运行时对象
        self._zt: Optional[ZeppTool] = None
        self._log_capture: Optional[GNSSLogCapture] = None
        self._results: dict[str, list[dict]] = {}
        self._need_reboot = False

        logger.info(f"Desense 测试初始化完成，共 {len(self.test_cases)} 个启用的测试用例")

    def setup(self) -> None:
        """测试准备"""
        # 创建带时间戳的日志目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_log_dir = Path(self.local_log_dir) / timestamp
        session_log_dir.mkdir(parents=True, exist_ok=True)
        self._session_log_dir = session_log_dir

        # 连接设备
        self._zt = ZeppTool(self.device_id)
        self._zt.connect()

        # 初始化日志采集器
        self._log_capture = GNSSLogCapture(
            zepp_tool=self._zt,
            local_log_dir=str(session_log_dir),
            device_log_dir=self.device_log_dir
        )

        logger.info(f"测试会话日志目录: {session_log_dir}")

    def teardown(self) -> None:
        if self._zt:
            self._zt.disconnect()

    def run(self) -> dict[str, list[dict]]:
        total_start = time.perf_counter()

        try:
            self._wait_for_positioning()
            for case in self.test_cases:
                self._run_single_case(case)

        except Exception as e:
            logger.error(f"测试执行出错: {e}")
            raise

        total_duration = time.perf_counter() - total_start
        logger.info(f"测试总耗时: {format_duration(total_duration)}")

        return self._results

    def _wait_for_positioning(self) -> bool:
        """
        发送定位指令，再通过导出 Terminal 的 log 并解析判断是否定位成功
        :return:
        """
        logger.info("开始等待 GNSS 定位...")

        # 发送定位命令
        for cmd in self.pos_cmd:
            self._zt.send_command(cmd)
            time.sleep(1)

        # 轮询检查定位状态
        attempt = 1
        while True:
            time.sleep(self.pos_scan_interval)

            log_path = self._log_capture.capture_terminal_log(
                rename_prefix=f"positioning-{attempt}-"
            )

            if not log_path:
                attempt += 1
                continue

            with open(log_path, 'r', encoding='utf-8') as f:
                log_text = f.read()

            gnss_data = parse_terminal_gnss_log(
                log_text,
                gnss_modes=self.gnss_modes,
                block_num=-1
            )

            if gnss_data and self._check_positioning_complete(gnss_data[-1]):
                logger.info("GNSS 定位成功")
                return True

            logger.debug(f"定位尝试 {attempt}，继续等待...")
            attempt += 1

    def _check_positioning_complete(self, gnss_record: dict) -> bool:
        """检查是否完成定位"""
        if gnss_record.get('pos_ttff', 0) <= 0:
            return False

        for mode in self.gnss_modes:
            gsv = gnss_record.get(f'{mode}_gsv', [])
            if len(gsv) < 4:
                return False

        return True

    def _run_single_case(self, case: DesenseTestCase) -> DesenseTestResult:
        """
        执行单个测试用例

        Args:
            case: 测试用例

        Returns:
            测试结果
        """
        logger.info(f"开始测试: {case.name} - {case.description}")
        start_time = datetime.now()

        try:
            # 检查是否需要重启
            if self._need_reboot:
                self._perform_reboot()
                self._need_reboot = False
                self._wait_for_positioning()

            # 发送开始命令
            if case.start_cmd:
                for cmd in case.start_cmd:
                    self._zt.send_command(cmd)
                    time.sleep(1)

            # 等待启动延迟
            if case.start_delay > 0:
                logger.debug(f"等待启动延迟: {case.start_delay}秒")
                time.sleep(case.start_delay)

            # 采集 NMEA 数据
            duration = case.duration or self.default_duration
            self._zt.collect_nmea_data(duration=duration)

            # 拉取日志
            log_path = self._log_capture.capture_nmea_log(
                rename_prefix=f"{case.log_prefix}-"
            )

            # 发送结束命令
            if case.end_cmd:
                for cmd in case.end_cmd:
                    self._zt.send_command(cmd)
                    time.sleep(1)

            # 标记是否需要重启
            if case.need_reboot:
                self._need_reboot = True

            # 解析数据
            if log_path:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_text = f.read()

                nmea_data = parse_nmea_log(log_text, gnss_modes=self.gnss_modes)
                gnss_infos = convert_nmea_to_gnss_info(nmea_data, gnss_modes=self.gnss_modes)
            else:
                gnss_infos = []

            # 保存结果
            self._results[case.name] = gnss_infos

            end_time = datetime.now()
            result = DesenseTestResult(
                case_name=case.name,
                gnss_infos=gnss_infos,
                start_time=start_time,
                end_time=end_time,
                success=True
            )

            logger.info(f"测试完成: {case.name}，采集到 {len(gnss_infos)} 条记录")
            return result

        except Exception as e:
            logger.error(f"测试用例 {case.name} 执行失败: {e}")
            return DesenseTestResult(
                case_name=case.name,
                gnss_infos=[],
                start_time=start_time,
                end_time=datetime.now(),
                success=False,
                error_message=str(e)
            )

    def _perform_reboot(self) -> None:
        """执行设备重启"""
        logger.info("执行设备重启...")
        self._zt.send_command(self.reboot_cmd)
        time.sleep(self.reboot_time)
        logger.info("设备重启完成")

    def get_results(self) -> dict[str, list[dict]]:
        """获取测试结果"""
        return self._results

    @property
    def session_log_dir(self) -> Path:
        """获取当前会话的日志目录"""
        return self._session_log_dir