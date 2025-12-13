"""
Zepp Tool 控制模块
通过 uiautomator2 控制 Android 设备上的 Zepp Tool 应用
"""

import time
from typing import Optional

import uiautomator2 as u2

from src.core.base_instrument import BaseInstrument
from src.core.exceptions import InstrumentError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ZeppTool(BaseInstrument):
    """
    Zepp Tool 应用控制类
    支持 Terminal 和 Data Collector 两个界面的切换和操作
    """

    # UI 元素定义
    UI_SEND_BUTTON = "发送"
    UI_START_COLLECT = "开始采集"
    UI_END_COLLECT = "结束采集"
    UI_DATA_COLLECT = "数据采集"
    UI_BASIC_INFO = "基本信息展示"
    UI_SELF_TEST = "自检工具"
    UI_SELF_TERMINAL = "自检终端"
    UI_SWITCH_MODE = "切换用户模式"
    UI_CANCEL = "取消"
    UI_OK = "好的"
    UI_MORE_OPTIONS = "更多选项"
    UI_EXPORT_LOG = "导出操作日志"
    UI_SENSOR_TYPE = "传感器数据类型(GSENSOR)"
    UI_GSENSOR = "(GSENSOR)加速传感器"
    UI_NMEA = "(NMEA)GPS NMEA数据"

    # Resource ID
    RES_TERM_ENTRY = "com.xiaomi.hm.health.bletool:id/term_entry"
    RES_TERM_SEND = "com.xiaomi.hm.health.bletool:id/term_entry_send"

    def __init__(self, device_id: str, wait_timeout: float = 10.0):
        """
        初始化 Zepp Tool 控制器

        Args:
            device_id: Android 设备 ID
            wait_timeout: UI 操作超时时间（秒）
        """
        super().__init__()
        self.device_id = device_id
        self.wait_timeout = wait_timeout
        self.d: Optional[u2.Device] = None
        self._operation_delay = 1.0  # 操作间延迟

    def connect(self) -> bool:
        """连接到 Android 设备"""
        try:
            self.d = u2.connect(self.device_id)
            self.d.implicitly_wait(self.wait_timeout)
            device_info = self.d.info
            logger.info(f"已连接到设备: {self.device_id}")
            logger.debug(f"设备信息: {device_info.get('productName', 'Unknown')}")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"连接设备失败: {e}")
            raise InstrumentError(f"无法连接到设备 {self.device_id}: {e}")

    def disconnect(self) -> None:
        """断开设备连接"""
        if self.d:
            self.d = None
            self._connected = False
            logger.info(f"已断开设备连接: {self.device_id}")

    def _delay(self, seconds: Optional[float] = None) -> None:
        """操作延迟"""
        time.sleep(seconds or self._operation_delay)

    def _is_in_terminal(self) -> bool:
        """检查是否在 Terminal 界面"""
        return self.d(text=self.UI_SEND_BUTTON).exists(timeout=2)

    def _is_in_data_collector(self) -> bool:
        """检查是否在 Data Collector 界面"""
        return self.d(text=self.UI_START_COLLECT).exists(timeout=2)

    def _navigate_to_terminal(self) -> bool:
        """
        从 Data Collector 导航到 Terminal 界面

        Returns:
            是否成功导航
        """
        try:
            self.d.press("back")
            self._delay()

            # 点击左上角菜单
            self.d.xpath('//*[contains(@text, "Cologne")]/preceding-sibling::*[1]').click()
            self._delay()

            self.d(text=self.UI_BASIC_INFO).click()
            self._delay()

            # 处理可能出现的模式切换对话框
            if self.d(text=self.UI_SWITCH_MODE).exists(timeout=2):
                self.d(text=self.UI_CANCEL).click()
                self._delay()

            self.d(text=self.UI_SELF_TEST).click()
            self._delay()

            self.d(text=self.UI_SELF_TERMINAL).click()
            self._delay()

            logger.debug("已导航到 Terminal 界面")
            return True
        except Exception as e:
            logger.error(f"导航到 Terminal 失败: {e}")
            return False

    def _navigate_to_data_collector(self) -> bool:
        """
        从 Terminal 导航到 Data Collector 界面

        Returns:
            是否成功导航
        """
        try:
            self.d.press("back")
            self._delay()

            # 点击左上角菜单
            self.d.xpath('//*[contains(@text, "Cologne")]/preceding-sibling::*[1]').click()
            self._delay()

            self.d(text=self.UI_DATA_COLLECT).click()
            self._delay()

            self.d(text=self.UI_DATA_COLLECT).click()
            self._delay()

            # 配置传感器类型
            self.d(text=self.UI_SENSOR_TYPE).click()
            self._delay()

            # 取消选择 GSENSOR，选择 NMEA
            gsensor = self.d(text=self.UI_GSENSOR)
            nmea = self.d(text=self.UI_NMEA)

            if gsensor.exists() and gsensor.info.get('checked', False):
                gsensor.click()
                self._delay()

            if nmea.exists() and not nmea.info.get('checked', False):
                nmea.click()
                self._delay()

            self.d(text=self.UI_OK).click()
            self._delay()

            logger.debug("已导航到 Data Collector 界面")
            return True
        except Exception as e:
            logger.error(f"导航到 Data Collector 失败: {e}")
            return False

    def ensure_terminal(self) -> bool:
        """
        确保当前在 Terminal 界面

        Returns:
            是否成功进入 Terminal 界面
        """
        if self._is_in_terminal():
            return True
        if self._is_in_data_collector():
            return self._navigate_to_terminal()
        logger.warning("无法确定当前界面状态")
        return False

    def ensure_data_collector(self) -> bool:
        """
        确保当前在 Data Collector 界面

        Returns:
            是否成功进入 Data Collector 界面
        """
        if self._is_in_data_collector():
            return True
        if self._is_in_terminal():
            return self._navigate_to_data_collector()
        logger.warning("无法确定当前界面状态")
        return False

    def send_command(self, cmd: str) -> bool:
        """
        在 Terminal 界面发送命令

        Args:
            cmd: 要发送的命令

        Returns:
            是否成功发送
        """
        if not cmd:
            return True

        if not self.ensure_terminal():
            logger.error("无法进入 Terminal 界面")
            return False

        try:
            self.d(resourceId=self.RES_TERM_ENTRY).set_text(cmd)
            self._delay()

            self.d(resourceId=self.RES_TERM_SEND).click()
            self._delay()

            logger.info(f"已发送命令: {cmd}")
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False

    def send_commands(self, commands: list[str]) -> bool:
        """
        批量发送命令

        Args:
            commands: 命令列表

        Returns:
            是否全部成功发送
        """
        for cmd in commands:
            if not self.send_command(cmd):
                return False
        return True

    def export_terminal_log(self) -> bool:
        """
        导出 Terminal 日志

        Returns:
            是否成功导出
        """
        if not self.ensure_terminal():
            return False

        try:
            self.d(description=self.UI_MORE_OPTIONS).click()
            self._delay()

            self.d(text=self.UI_EXPORT_LOG).click()
            self._delay()

            logger.info("已导出 Terminal 日志")
            return True
        except Exception as e:
            logger.error(f"导出日志失败: {e}")
            return False

    def collect_nmea_data(self, duration: int) -> bool:
        """
        采集 NMEA 数据

        Args:
            duration: 采集持续时间（秒）

        Returns:
            是否成功采集
        """
        if not self.ensure_data_collector():
            logger.error("无法进入 Data Collector 界面")
            return False

        try:
            self.d(text=self.UI_START_COLLECT).click()
            logger.info(f"开始采集 NMEA 数据，持续 {duration} 秒")

            time.sleep(duration)

            self.d(text=self.UI_END_COLLECT).click()
            self._delay()

            logger.info("NMEA 数据采集完成")
            return True
        except Exception as e:
            logger.error(f"NMEA 数据采集失败: {e}")
            return False

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        """
        从设备拉取文件

        Args:
            remote_path: 设备上的文件路径
            local_path: 本地保存路径

        Returns:
            是否成功拉取
        """
        try:
            self.d.pull(remote_path, local_path)
            logger.debug(f"已拉取文件: {remote_path} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"拉取文件失败: {e}")
            return False

    def shell(self, command: str) -> str:
        """
        执行 shell 命令

        Args:
            command: shell 命令

        Returns:
            命令输出
        """
        result = self.d.shell(command)
        return result.output.strip()

    def list_files(self, directory: str) -> list[str]:
        """
        列出目录中的文件

        Args:
            directory: 目录路径

        Returns:
            文件名列表
        """
        output = self.shell(f'ls -1 {directory}')
        return output.splitlines() if output else []