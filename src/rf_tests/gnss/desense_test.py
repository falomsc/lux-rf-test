import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.exceptions import PosMaxAttemptError, RebootMaxAttemptError
from src.core.base_test import BaseTest
from src.instruments.zepp_tool import ZeppTool
from src.rf_tests.gnss.log_capture import GNSSLogCapture
from src.rf_tests.gnss.log_parser import (
    parse_term_records,
    parse_nmea_records,
    convert_nmea_records_to_gnss_records,
    TermRecord
)
from src.utils.logger import get_logger
from src.utils.time_utils import format_duration

logger = get_logger()


@dataclass
class DesenseTestCase:
    name: str
    description: str = ""
    start_cmds: list[str] = field(default_factory=list)
    end_cmds: list[str] = field(default_factory=list)
    start_delay: int = 0
    need_reboot: bool = False
    duration: int = 30
    log_prefix: str = ""
    enabled: bool = True

    @classmethod
    def from_dict(cls, name: str, data: dict) -> 'DesenseTestCase':
        start_cmds = data.get('start_cmds', [])
        end_cmds = data.get('end_cmds', [])

        return cls(
            name=name,
            description=data.get('description', ''),
            start_cmds=start_cmds,
            end_cmds=end_cmds,
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
    gnss_records: list[dict]
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
        self.local_log_dir = device_cfg.get('local_log_dir', './output/gnss_desense/logs/{timestamp}')

        # 测试参数
        test_params = config.get('test_params', {})
        self.pos_scan_interval = test_params.get('pos_scan_interval', 30)
        self.pos_scan_max_attempt = test_params.get('pos_scan_max_attempt', 20)
        self.reboot_time = test_params.get('reboot_time', 60)
        self.reboot_max_attempt = test_params.get('reboot_max_attempt', 10)

        # GNSS 配置
        generic_commands = config.get('generic_commands', {})
        self.gnss_open_cmd = generic_commands.get('gnss_open_cmd', '')
        self.read_auto_cmd = generic_commands.get('read_auto_cmd', '')
        self.reboot_cmd = generic_commands.get('reboot_cmd', 'hm:sft+power=reboot')
        gnss_modes = config.get('gnss_modes', ['gps', 'bds', 'gal', 'gln'])
        self.gnss_modes = tuple(gnss_modes)

        # 日志格式
        self.log_formats = config.get('log_formats', ['json', 'xlsx', 'dashboard'])

        # 加载测试用例
        self.test_cases: list[DesenseTestCase] = []
        for name, case_config in config.get('test_cases', {}).items():
            case = DesenseTestCase.from_dict(name, case_config)
            if case.enabled:
                self.test_cases.append(case)

        # 运行时对象
        self._zt: ZeppTool | None = None
        self._log_capture: GNSSLogCapture | None = None
        self._results: dict[str, list[dict]] = {}
        self._need_reboot = False
        self._case_running_num = 0

        logger.info(f"Desense 测试初始化完成，共 {len(self.test_cases)} 个启用的测试用例")

    def setup(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        local_log_dir = Path(self.local_log_dir.format(timestamp=timestamp))
        local_log_dir.mkdir(parents=True, exist_ok=True)
        self._local_log_dir = local_log_dir

        # 连接设备
        self._zt = ZeppTool(self.device_id)
        self._zt.connect()
        self._log_capture = GNSSLogCapture(
            zepp_tool=self._zt,
            local_log_dir=self._local_log_dir,
            device_log_dir=self.device_log_dir
        )

        logger.info(f"本地日志目录: {self._local_log_dir}")

    def teardown(self) -> None:
        if self._zt:
            self._zt.disconnect()

    def run(self) -> dict[str, list[dict]]:
        total_start = time.perf_counter()

        try:
            self._open_gnss()
            self._read_auto()
            self._wait_for_positioning()
            for case in self.test_cases:
                self._run_single_case(case)

        except Exception as e:
            logger.error(f"测试执行出错: {e}")
            raise

        total_duration = time.perf_counter() - total_start
        logger.info(f"测试总耗时: {format_duration(total_duration)}")

        return self._results

    def _open_gnss(self):
        self._zt.send_command(self.gnss_open_cmd)

    def _read_auto(self):
        self._zt.send_command(self.read_auto_cmd)

    def _wait_for_positioning(self) -> bool:
        """
        导出 Terminal 的 log 并解析判断是否定位成功
        :return:
        """
        logger.info("开始等待 GNSS 定位...")
        pos_attempt = 1
        while True:
            logger.debug(f"第{pos_attempt}次定位尝试，继续等待...")
            time.sleep(self.pos_scan_interval)
            log_path = self._log_capture.capture_term_log(
                term_repl= fr"pos-{pos_attempt}-\g<0>"
            )

            if not log_path:
                pos_attempt += 1
                continue

            with open(log_path, 'r', encoding='utf-8') as f:
                log_text = f.read()

            term_records = parse_term_records(
                log_text=log_text,
                gnss_modes=self.gnss_modes,
                block_num=-1
            )

            if term_records and self._check_positioning_complete(term_records[-1]):
                logger.info("GNSS 定位成功")
                return True

            pos_attempt += 1
            if pos_attempt > self.pos_scan_max_attempt:
                logger.warning(f"GNSS 定位失败，尝试次数已用尽，最后一次尝试的记录：{term_records}")
                raise PosMaxAttemptError

    def _check_positioning_complete(self, term_records: TermRecord) -> bool:
        """检查是否完成定位"""
        if term_records.get('pos_ttff', 0) == 0:
            return False
        for mode in self.gnss_modes:
            gsv = term_records.get(f'{mode}_gsv', [])
            if len(gsv) < 4:
                return False
        return True

    def _run_single_case(self, case: DesenseTestCase) -> DesenseTestResult:
        """
        执行单个测试用例
        """
        logger.info(f"开始测试: {case.name} - {case.description}")
        start_time = datetime.now()

        try:
            # 1，卫星定位
            if self._need_reboot:
                self._perform_reboot()
                self._need_reboot = False
                self._open_gnss()
                self._read_auto()
                self._wait_for_positioning()
            elif self._case_running_num != 0:
                self._open_gnss()
                self._wait_for_positioning()

            # 2，发送开始测试指令
            if case.start_cmds:
                self._zt.send_commands(case.start_cmds, 1)

            # 3，采集NEMA数据
            self._zt.collect_nmea_data(duration=case.duration)

            # 4，发送结束测试指令
            if case.end_cmds:
                self._zt.send_commands(case.end_cmds, 1)
            if case.need_reboot:
                self._need_reboot = True

            # 5，从手机拷贝日志文件到PC
            log_path = self._log_capture.capture_nmea_log(
                nmea_repl=fr"test-{case.log_prefix}-\g<0>"
            )

            # 6，解析日志文件
            if log_path:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_text = f.read()
                nmea_data = parse_nmea_records(log_text, gnss_modes=self.gnss_modes)
                gnss_records = convert_nmea_records_to_gnss_records(nmea_data, gnss_modes=self.gnss_modes)
            else:
                gnss_records = []
            self._results[case.name] = gnss_records

            # 7，输出测试结果
            result = DesenseTestResult(
                case_name=case.name,
                gnss_records=gnss_records,
                start_time=start_time,
                end_time=datetime.now(),
                success=True
            )
            self._case_running_num += 1
            logger.info(f"{self._case_running_num}，测试完成: {case.name}，采集到 {len(gnss_records)} 条记录")
            return result

        except Exception as e:
            self._case_running_num += 1
            logger.error(f"{self._case_running_num}，测试用例 {case.name} 执行失败: {e}")
            return DesenseTestResult(
                case_name=case.name,
                gnss_records=[],
                start_time=start_time,
                end_time=datetime.now(),
                success=False,
                error_message=str(e)
            )

    def _perform_reboot(self) -> bool:
        """执行设备重启"""
        logger.info("执行设备重启...")
        self._zt.send_command(self.reboot_cmd)
        reboot_attempt = 1
        while True:
            time.sleep(self.reboot_time)
            if self._zt.is_term_connected():
                logger.info("设备重启完成")
                return True
            reboot_attempt += 1
            if reboot_attempt > self.reboot_max_attempt:
                logger.warning("设备重启失败")
                raise RebootMaxAttemptError


    def get_results(self) -> dict[str, list[dict]]:
        """获取测试结果"""
        return self._results

    @property
    def session_log_dir(self) -> Path:
        """获取当前会话的日志目录"""
        return self._local_log_dir
