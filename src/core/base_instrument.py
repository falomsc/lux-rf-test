from abc import ABC, abstractmethod
import time
import pyvisa
from pyvisa import VisaIOError

from src.core.exceptions import InstrumentError, ConnectionError


class BaseInstrument(ABC):
    """所有VISA仪表的基类"""

    def __init__(
        self,
        resource_address: str,
        timeout: int = 10000,
        write_termination: str = "\n",
        read_termination: str = "\n",
        sending_interval: float = 0.5
    ):
        self._address = resource_address
        self._timeout = timeout
        self._write_termination = write_termination
        self._read_termination = read_termination
        self._sending_interval = sending_interval
        self._rm: pyvisa.ResourceManager | None = None
        self._inst: pyvisa.Resource | None = None
        self._connected = False

    @property
    def address(self) -> str:
        return self._address

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> "BaseInstrument":
        """连接仪表"""
        try:
            self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(self._address)
            self._inst.timeout = self._timeout
            self._inst.write_termination = self._write_termination
            self._inst.read_termination = self._read_termination
            self._inst.query_delay = self._sending_interval
            self._connected = True

            # 验证连接
            idn = self.query("*IDN?")
            print(f"Connected to: {idn.strip()}")
            return self

        except VisaIOError as e:
            raise ConnectionError(f"无法连接仪表 {self._address}: {e}")

    def disconnect(self) -> None:
        """断开连接"""
        if self._inst:
            try:
                self._inst.close()
            except VisaIOError as e:
                print(f"关闭资源时出错: {e}")
            finally:
                self._connected = False

    def __enter__(self) -> "BaseInstrument":
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def __del__(self) -> None:
        self.disconnect()

    def write(self, command: str) -> None:
        """发送SCPI命令"""
        if not self._connected:
            raise InstrumentError("仪表未连接")
        self._inst.write(command)
        print(f"[-->{self._address}] {command}")
        if self._sending_interval:
            time.sleep(self._sending_interval)

    def read(self) -> str:
        """读取响应"""
        if not self._connected:
            raise InstrumentError("仪表未连接")
        response = self._inst.read()
        print(f"[<--{self._address}] {response}")
        return response

    def query(self, command: str, delay: float | None = None) -> str:
        """发送查询命令并读取响应"""
        if not self._connected:
            raise InstrumentError("仪表未连接")

        if delay is not None:
            old_delay = self._inst.query_delay
            self._inst.query_delay = delay
            try:
                return self._inst.query(command)
            finally:
                self._inst.query_delay = old_delay

        print(f"[-->{self._address}] {command}")
        response = self._inst.query(command)
        print(f"[<--{self._address}] {response}")
        return response

    def wait_opc(self) -> None:
        """等待操作完成"""
        self.query("*OPC?")

    @abstractmethod
    def reset(self) -> None:
        """重置仪表 - 子类实现"""
        pass

    @abstractmethod
    def preset(self) -> None:
        """预设仪表 - 子类实现"""
        pass