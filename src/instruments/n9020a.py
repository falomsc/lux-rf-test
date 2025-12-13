from src.core.base_instrument import BaseInstrument


class N9020A(BaseInstrument):
    """N9020A MXA Signal Analyzer 驱动"""

    def reset(self) -> None:
        """重置仪表"""
        self.write("*RST")
        self.wait_opc()

    def preset(self) -> None:
        """预设为频谱分析仪模式"""
        self.write(":INST SA")
        self.write(":SYST:PRES")
        self.write(":INIT:CONT OFF")
        self.write(":POW:ATT 0")
        self.wait_opc()

    # ========== 频率设置 ==========
    def set_frequency_range(self, start_hz: float, stop_hz: float) -> None:
        """设置频率范围"""
        self.write(f":SENS:FREQ:STAR {start_hz}")
        self.write(f":SENS:FREQ:STOP {stop_hz}")

    def set_center_frequency(self, freq_hz: float) -> None:
        """设置中心频率"""
        self.write(f":SENS:FREQ:CENT {freq_hz}")

    def set_span(self, span_hz: float) -> None:
        """设置频率跨度"""
        self.write(f":SENS:FREQ:SPAN {span_hz}")

    # ========== 带宽设置 ==========
    def set_rbw(self, rbw_hz: float) -> None:
        """设置分辨率带宽"""
        self.write(f":SENS:BAND:RES {rbw_hz}")

    def set_vbw(self, vbw_hz: float) -> None:
        """设置视频带宽"""
        self.write(f":SENS:BAND:VID {vbw_hz}")

    # ========== 幅度设置 ==========
    def set_reference_level(self, level_dbm: float) -> None:
        """设置参考电平"""
        self.write(f":DISP:WIND:TRAC:Y:RLEV {level_dbm}")

    def set_reference_offset(self, offset_db: float) -> None:
        """设置参考电平偏移"""
        self.write(f":DISP:WIND:TRAC:Y:RLEV:OFFS {offset_db}")

    def set_attenuation(self, atten_db: float) -> None:
        """设置衰减"""
        self.write(f":POW:ATT {atten_db}")

    # ========== 迹线设置 ==========
    def set_trace_mode(self, mode: str) -> None:
        """设置迹线模式: WRIT, MAXH, MINH, VIEW, BLAN, AVER"""
        self.write(f":TRAC:MODE {mode}")

    def set_average(self, enable: bool, count: int = 10) -> None:
        """设置平均"""
        self.write(f":SENS:AVER:STAT {'ON' if enable else 'OFF'}")
        if enable:
            self.write(f":SENS:AVER:COUN {count}")

    # ========== 触发与测量 ==========
    def set_continuous_sweep(self, enable: bool) -> None:
        """设置连续扫描"""
        self.write(f":INIT:CONT {'ON' if enable else 'OFF'}")

    def single_sweep(self) -> None:
        """执行单次扫描"""
        self.write(":INIT")
        self.wait_opc()

    # ========== Marker操作 ==========
    def marker_to_peak(self, marker: int = 1) -> None:
        """Marker移到峰值"""
        self.write(f":CALC:MARK{marker}:MAX")

    def marker_to_next_peak(self, marker: int = 1) -> None:
        """Marker移到下一个峰值"""
        self.write(f":CALC:MARK{marker}:MAX:NEXT")

    def set_marker_frequency(self, freq_hz: float, marker: int = 1) -> None:
        """设置Marker频率"""
        self.write(f":CALC:MARK{marker}:X {freq_hz}")

    def get_marker_x(self, marker: int = 1) -> float:
        """获取Marker X值（频率）"""
        return float(self.query(f":CALC:MARK{marker}:X?"))

    def get_marker_y(self, marker: int = 1) -> float:
        """获取Marker Y值（幅度）"""
        return float(self.query(f":CALC:MARK{marker}:Y?"))

    def get_peak_marker(self, marker: int = 1) -> tuple[float, float]:
        """获取峰值Marker的频率和幅度"""
        self.marker_to_peak(marker)
        freq_hz = self.get_marker_x(marker)
        power_dbm = self.get_marker_y(marker)
        return freq_hz, power_dbm

    # ========== 截图 ==========
    def save_screenshot(self, filepath: str) -> None:
        """保存屏幕截图"""
        self.write(f':MMEM:STOR:SCR "{filepath}"')
        print(f"Screenshot saved -> {filepath}")

    # ========== 迹线数据 ==========
    def get_trace_data(self, trace: int = 1) -> list[float]:
        """获取迹线数据"""
        data = self.query(f":TRAC:DATA? TRACE{trace}")
        return [float(x) for x in data.split(",")]