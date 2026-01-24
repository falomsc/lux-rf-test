from dataclasses import dataclass, field
from typing import Any
import os

from src.core.base_test import BaseTest
from src.instruments.n9020a import N9020A
from src.core.exceptions import TestError


@dataclass
class SpuriousBand:
    """杂散测试频段定义"""
    name: str
    start_hz: float
    stop_hz: float
    rbw_hz: float
    offset_db: float
    limit_dbm: float

    # 测量结果
    measured_peak_dbm: float | None = None
    measured_peak_freq_mhz: float | None = None
    pass_fail: bool | None = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "band_name": self.name,
            "start_mhz": self.start_hz / 1e6,
            "stop_mhz": self.stop_hz / 1e6,
            "rbw_khz": self.rbw_hz / 1e3,
            "limit_dbm": self.limit_dbm,
            "measured_peak_dbm": self.measured_peak_dbm,
            "measured_peak_freq_mhz": self.measured_peak_freq_mhz,
            "pass_fail": self.pass_fail
        }


class BluetoothSpuriousTest(BaseTest):
    """蓝牙杂散发射测试"""

    def __init__(self, config: dict[str, Any], instrument_config: dict[str, Any]):
        super().__init__(config)
        self._instrument_config = instrument_config
        self._analyzer: N9020A | None = None
        self._bands: list[SpuriousBand] = []
        self._exclude_ranges: list[tuple[float, float]] = []
        self._channel: int = 0
        self._screenshots_folder: str = ""
        self._parse_config()

    def _parse_config(self) -> None:
        """解析配置"""
        # 解析测试参数
        test_cfg = self.config.get("test", {})
        self._channel = test_cfg.get("channel", 0)
        self._screenshots_folder = test_cfg.get("screenshots_folder", "output/screenshots")

        # 解析频段
        for band_cfg in self.config.get("bands", []):
            band = SpuriousBand(
                name=band_cfg["name"],
                start_hz=band_cfg["start_hz"],
                stop_hz=band_cfg["stop_hz"],
                rbw_hz=band_cfg["rbw_hz"],
                offset_db=band_cfg["offset_db"],
                limit_dbm=band_cfg["limit_dbm"]
            )
            self._bands.append(band)

        # 解析排除频段
        for exclude in self.config.get("exclude", []):
            self._exclude_ranges.append((exclude[0], exclude[1]))

    def setup(self) -> None:
        """测试准备"""
        # 创建截图目录
        os.makedirs(self._screenshots_folder, exist_ok=True)

        # 连接仪表
        n9020a_cfg = self._instrument_config.get("n9020a", {})
        self._analyzer = N9020A(
            resource_address=n9020a_cfg["resource"],
            timeout=n9020a_cfg.get("timeout", 20000),
            sending_interval=n9020a_cfg.get("sending_interval", 0.05)
        )
        self._analyzer.connect()
        self._analyzer.preset()

    def execute(self) -> None:
        """执行测试"""
        for band in self._bands:
            self._measure_band(band)
            self._capture_screenshot(band)
            self.results.append(band.to_dict())

        self._print_summary()

    def teardown(self) -> None:
        """测试清理"""
        if self._analyzer:
            self._analyzer.disconnect()

    def _measure_band(self, band: SpuriousBand) -> None:
        """测量单个频段"""
        # 检查是否完全在排除范围内
        if self._is_fully_excluded(band):
            raise TestError(f"频段 {band.name} 完全在排除范围内!")

        analyzer = self._analyzer

        # 配置仪表
        analyzer.set_frequency_range(band.start_hz, band.stop_hz)
        analyzer.set_rbw(band.rbw_hz)
        analyzer.set_reference_offset(band.offset_db)
        analyzer.set_average(False)
        analyzer.set_trace_mode("WRIT")
        analyzer.set_continuous_sweep(False)

        # 初始扫描
        analyzer.single_sweep()

        # Max Hold扫描
        analyzer.set_trace_mode("MAXH")
        analyzer.single_sweep()

        # 获取峰值
        analyzer.marker_to_peak()
        peak_dbm = analyzer.get_marker_y()
        peak_freq_hz = analyzer.get_marker_x()

        # 如果峰值在排除范围内，查找下一个峰值
        while self._is_in_exclude(peak_freq_hz):
            analyzer.marker_to_next_peak()
            new_peak_dbm = analyzer.get_marker_y()
            new_peak_freq_hz = analyzer.get_marker_x()

            # 检查是否找到新峰值
            if abs(new_peak_freq_hz - peak_freq_hz) < 1e-3:
                break
            peak_freq_hz, peak_dbm = new_peak_freq_hz, new_peak_dbm

        # 如果仍在排除范围内，使用边界值
        if self._is_in_exclude(peak_freq_hz):
            peak_dbm, peak_freq_hz = self._get_border_peak(band)

        # 记录结果
        band.measured_peak_dbm = peak_dbm
        band.measured_peak_freq_mhz = peak_freq_hz / 1e6
        band.pass_fail = peak_dbm <= band.limit_dbm

        # 打印结果
        status = "PASS" if band.pass_fail else "FAIL"
        print(f"[{band.name}] Peak = {band.measured_peak_dbm:6.2f} dBm  "
              f"Freq = {band.measured_peak_freq_mhz:.3f} MHz  "
              f"Limit = {band.limit_dbm:5.1f} dBm  {status}")

    def _capture_screenshot(self, band: SpuriousBand) -> None:
        """截图"""
        filename = f"{self._screenshots_folder}/{self._channel}_{band.name}.png"
        self._analyzer.save_screenshot(filename)

    def _is_in_exclude(self, freq_hz: float) -> bool:
        """判断频率是否在排除范围内"""
        return any(lo <= freq_hz <= hi for lo, hi in self._exclude_ranges)

    def _is_fully_excluded(self, band: SpuriousBand) -> bool:
        """判断频段是否完全在排除范围内"""
        return any(
            band.start_hz >= lo and band.stop_hz <= hi
            for lo, hi in self._exclude_ranges
        )

    def _get_border_peak(self, band: SpuriousBand) -> tuple[float, float]:
        """获取排除边界处的峰值"""
        borders = []
        for lo, hi in self._exclude_ranges:
            if hi < band.start_hz or lo > band.stop_hz:
                continue
            if band.start_hz < lo < band.stop_hz:
                borders.append(lo)
            if band.start_hz < hi < band.stop_hz:
                borders.append(hi)

        best_dbm, best_freq = -1e99, 0.0
        for freq in borders:
            self._analyzer.set_marker_frequency(freq)
            dbm = self._analyzer.get_marker_y()
            if dbm > best_dbm:
                best_dbm, best_freq = dbm, freq

        return best_dbm, best_freq

    def _print_summary(self) -> None:
        """打印测试汇总"""
        print(f"\n{'='*60}")
        print("Spurious Test Summary")
        print(f"{'='*60}")

        overall = True
        for band in self._bands:
            status = "PASS" if band.pass_fail else "FAIL"
            print(f"{band.name:<25} {band.measured_peak_freq_mhz:>10.3f} MHz  "
                  f"{band.measured_peak_dbm:>7.2f} dBm  "
                  f"Limit {band.limit_dbm:>6.1f}  -> {status}")
            overall &= bool(band.pass_fail)

        print(f"\n{'='*60}")
        print(f"Overall Result: {'PASS ✓' if overall else 'FAIL ✗'}")
        print(f"{'='*60}\n")