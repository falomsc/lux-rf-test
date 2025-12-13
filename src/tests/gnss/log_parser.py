"""
GNSS 日志解析模块
支持 NMEA 和 Terminal 日志的解析
"""

import re
from datetime import datetime, time as dt_time
from typing import Literal, Sequence, Optional, TypedDict

import pynmea2

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 类型定义
AllowedMode = Literal["gps", "bds", "gal", "gln"]

# Talker ID 到 GNSS 模式的映射
TALKER_TO_MODE: dict[str, AllowedMode] = {
    "GP": "gps",
    "GL": "gln",
    "GA": "gal",
    "GB": "bds",
    "BD": "bds"
}


class Sat(TypedDict):
    """卫星基本信息"""
    prn: str
    snr: float


class NMEASat(TypedDict):
    """NMEA 卫星详细信息"""
    prn: str
    elev: int
    azimuth: int
    snr: float


class TermGNSSRecord(TypedDict):
    """Terminal 日志中的 GNSS 记录"""
    utc_time: str
    start: str
    top4_cn: float
    pos_sta: str
    pos_ttff: int
    use_num: int
    total_sv_num: int
    gps_gsv: list[Sat]
    bds_gsv: list[Sat]
    gal_gsv: list[Sat]
    gln_gsv: list[Sat]


class NMEARecord(TypedDict):
    """NMEA 解析后的完整记录"""
    utc_time: Optional[dt_time]
    datetime: Optional[datetime]
    latitude: float
    longitude: float
    altitude: float
    speed_kph: float
    course: float
    num_sats: int
    hdop: float
    pdop: float
    vdop: float
    status: str
    gsv_infos: dict[str, list[NMEASat]]


class GsvInfo(TypedDict):
    """GSV 信息"""
    top4_cn: Optional[float]
    sats: list[Sat]


class GNSSRecord(TypedDict):
    """处理后的 GNSS 记录"""
    utc_time: str
    status: str
    overall: dict
    gps_gsv: GsvInfo
    bds_gsv: GsvInfo
    gal_gsv: GsvInfo
    gln_gsv: GsvInfo


def parse_terminal_gnss_log(
    log_text: str,
    gnss_modes: Sequence[AllowedMode] = ("gps", "bds", "gal", "gln"),
    block_num: Optional[int] = None,
    positive_ttff: bool = False,
    start_marker: Optional[str] = None,
    end_marker: Optional[str] = None,
    start_delay: int = 0
) -> list[TermGNSSRecord]:
    """
    从 Terminal 日志中提取 GNSS 信息

    Args:
        log_text: 日志文本
        gnss_modes: 要提取的 GNSS 模式
        block_num: 指定提取第几个 GNSS INFO 块（None 表示全部）
        positive_ttff: 是否只提取 ttff > 0 的记录
        start_marker: 开始解析的标记
        end_marker: 结束解析的标记
        start_delay: 从 start_marker 开始跳过的记录数

    Returns:
        GNSS 记录列表
    """
    # 处理起止标记
    if start_marker:
        m_start = re.search(re.escape(start_marker), log_text)
        if not m_start:
            return []
        log_text = log_text[m_start.end():]

    if end_marker:
        m_end = re.search(re.escape(end_marker), log_text)
        if not m_end:
            return []
        log_text = log_text[:m_end.start()]

    # GNSS INFO 解析正则表达式
    pattern = re.compile(r"""
        GNSS\ INFO:
        \s*utc\ time:\s+(\d{2}:\d{2}:\d{2}).*?
        start\ Mode:\s+(\w+)\s+top4_cn:\s+([\d.]+).*?
        pos_sta:\s+(\w+)\s+pos_ttff:\s+(\d+).*?
        use_num:\s+(\d+)\s+total_sv_num:\s+(\d+).*?
        gps_gsv_info:\s*
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
        bds_gsv_info:\s*
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
        gal_gsv_info:\s*
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
        gln_gsv_info:\s*
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+).*?
            L1\s+(\d+)\s+([\d.]+)
    """, re.VERBOSE | re.DOTALL)

    term_gnss_data = []
    seen_times = set()
    blocks = re.split(r'(?=GNSS INFO:)', log_text)

    if block_num is not None:
        try:
            blocks = [blocks[block_num]]
        except IndexError:
            return []

    delay_counter = start_delay
    for block in blocks:
        if delay_counter > 0:
            delay_counter -= 1
            continue

        if 'GNSS INFO:' not in block:
            continue

        m = pattern.search(block)
        if not m:
            continue

        pos_ttff = int(m.group(5))
        if positive_ttff and pos_ttff == 0:
            continue

        utc_time = m.group(1)
        if utc_time in seen_times:
            continue
        seen_times.add(utc_time)

        gnss_info = {
            "utc_time": utc_time,
            "start": m.group(2),
            "top4_cn": float(m.group(3)),
            "pos_sta": m.group(4),
            "pos_ttff": pos_ttff,
            "use_num": int(m.group(6)),
            "total_sv_num": int(m.group(7))
        }

        # 提取各星座的 GSV 信息
        gsv_data = {
            "gps_gsv": [(8, 9), (10, 11), (12, 13), (14, 15)],
            "bds_gsv": [(16, 17), (18, 19), (20, 21), (22, 23)],
            "gal_gsv": [(24, 25), (26, 27), (28, 29), (30, 31)],
            "gln_gsv": [(32, 33), (34, 35), (36, 37), (38, 39)]
        }

        for mode in gnss_modes:
            key = f"{mode}_gsv"
            if key in gsv_data:
                gnss_info[key] = [
                    {"prn": m.group(idx[0]), "snr": float(m.group(idx[1]))}
                    for idx in gsv_data[key]
                ]

        term_gnss_data.append(gnss_info)

    logger.debug(f"解析到 {len(term_gnss_data)} 条 Terminal GNSS 记录")
    return term_gnss_data


def parse_nmea_log(
    log_text: str,
    gnss_modes: Sequence[AllowedMode] = ("gps", "bds", "gal", "gln")
) -> list[NMEARecord]:
    """
    解析 NMEA 日志

    Args:
        log_text: NMEA 日志文本
        gnss_modes: 要解析的 GNSS 模式

    Returns:
        NMEA 记录列表
    """
    nmea_data: list[NMEARecord] = []
    current_record: Optional[NMEARecord] = None
    current_time_str: Optional[str] = None
    gnss_modes_set = set(gnss_modes)

    def create_empty_record(msg_time: dt_time) -> NMEARecord:
        return {
            "utc_time": msg_time,
            "datetime": None,
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
            "speed_kph": 0.0,
            "course": 0.0,
            "num_sats": 0,
            "hdop": 0.0,
            "pdop": 0.0,
            "vdop": 0.0,
            "status": "V",
            "gsv_infos": {f"{mode}_gsv": [] for mode in gnss_modes}
        }

    for line in log_text.strip().split('\n'):
        line = line.strip()

        # 跳过非 NMEA 语句和厂商自定义语句
        if not line.startswith('$') or line.startswith('$PAIRACC'):
            continue

        try:
            msg = pynmea2.parse(line)
        except pynmea2.ParseError:
            continue

        # 获取时间戳，用于分组记录
        msg_time = getattr(msg, 'timestamp', None)
        if msg_time is not None:
            time_str = str(msg_time)
            if time_str != current_time_str:
                if current_record is not None:
                    nmea_data.append(current_record)
                current_time_str = time_str
                current_record = create_empty_record(msg_time)

        if current_record is None:
            continue

        # 解析不同类型的 NMEA 语句
        if isinstance(msg, pynmea2.types.talker.GGA):
            current_record['latitude'] = msg.latitude
            current_record['longitude'] = msg.longitude
            current_record['altitude'] = msg.altitude or 0.0
            current_record['num_sats'] = int(msg.num_sats) if msg.num_sats else 0
            current_record['hdop'] = float(msg.horizontal_dil) if msg.horizontal_dil else 0.0

        elif isinstance(msg, pynmea2.types.talker.GSA):
            current_record['pdop'] = float(msg.pdop) if msg.pdop else current_record['pdop']
            current_record['hdop'] = float(msg.hdop) if msg.hdop else current_record['hdop']
            current_record['vdop'] = float(msg.vdop) if msg.vdop else current_record['vdop']

        elif isinstance(msg, pynmea2.types.talker.GSV):
            mode = TALKER_TO_MODE.get(msg.talker)
            if mode is None or mode not in gnss_modes_set:
                continue

            gsv_key = f"{mode}_gsv"
            for i in range(1, 5):
                prn = getattr(msg, f'sv_prn_num_{i}', None)
                snr = getattr(msg, f'snr_{i}', None)
                if not prn or not snr:
                    continue
                try:
                    elev = getattr(msg, f'elevation_deg_{i}', None)
                    azim = getattr(msg, f'azimuth_{i}', None)
                    current_record['gsv_infos'][gsv_key].append({
                        "prn": prn,
                        "elev": int(elev) if elev else 0,
                        "azimuth": int(azim) if azim else 0,
                        "snr": float(snr)
                    })
                except (ValueError, TypeError):
                    continue

        elif isinstance(msg, pynmea2.types.talker.RMC):
            if current_record['utc_time'] and msg.datestamp:
                current_record['datetime'] = datetime.combine(
                    msg.datestamp, current_record['utc_time']
                )
            if msg.spd_over_grnd:
                current_record['speed_kph'] = float(msg.spd_over_grnd) * 1.852
            if msg.true_course:
                current_record['course'] = float(msg.true_course)
            if msg.status:
                current_record['status'] = msg.status

    # 添加最后一条记录
    if current_record:
        nmea_data.append(current_record)

    logger.debug(f"解析到 {len(nmea_data)} 条 NMEA 记录")
    return nmea_data


def calculate_top4_cn(
    sats: list[dict],
    include_constellation: bool = False
) -> tuple[Optional[float], list[dict]]:
    """
    计算 Top4 载噪比平均值

    Args:
        sats: 卫星列表
        include_constellation: 是否在结果中包含星座信息

    Returns:
        (top4_cn 平均值, top4 卫星列表)
    """
    valid_sats = [s for s in sats if s.get('snr') is not None]
    if not valid_sats:
        return None, []

    top4_sats = sorted(valid_sats, key=lambda x: x['snr'], reverse=True)[:4]
    top4_cn = round(sum(s['snr'] for s in top4_sats) / len(top4_sats), 2)

    if include_constellation:
        result_sats = [
            {"prn": s["prn"], "snr": s["snr"], "constellation": s.get("constellation", "")}
            for s in top4_sats
        ]
    else:
        result_sats = [{"prn": s["prn"], "snr": s["snr"]} for s in top4_sats]

    return top4_cn, result_sats


def convert_nmea_to_gnss_info(
    nmea_data: list[NMEARecord],
    gnss_modes: Sequence[AllowedMode] = ("gps", "bds", "gal", "gln")
) -> list[GNSSRecord]:
    """
    将 NMEA 数据转换为 GNSS 信息格式

    Args:
        nmea_data: NMEA 记录列表
        gnss_modes: GNSS 模式列表

    Returns:
        GNSS 信息列表
    """
    gnss_infos = []

    for nmea_record in nmea_data:
        utc_time = nmea_record['utc_time']
        current_record = {
            "utc_time": utc_time.strftime("%H:%M:%S") if utc_time else None,
            "status": nmea_record['status'],
            "overall": {"top4_cn": None, "sats": []},
        }

        gsv_infos = nmea_record.get('gsv_infos', {})
        all_sats = []

        for mode in gnss_modes:
            mode_key = f"{mode}_gsv"
            mode_sats = gsv_infos.get(mode_key, [])
            top4_cn, sats = calculate_top4_cn(mode_sats)
            current_record[mode_key] = {"top4_cn": top4_cn, "sats": sats}

            # 收集所有卫星用于计算总体 top4
            all_sats.extend(
                {"prn": s["prn"], "snr": s["snr"], "constellation": mode}
                for s in mode_sats if s.get("snr") is not None
            )

        # 计算总体 top4
        overall_top4_cn, overall_sats = calculate_top4_cn(
            all_sats, include_constellation=True
        )
        current_record["overall"]["top4_cn"] = overall_top4_cn
        current_record["overall"]["sats"] = overall_sats

        gnss_infos.append(current_record)

    logger.debug(f"转换得到 {len(gnss_infos)} 条 GNSS 信息记录")
    return gnss_infos