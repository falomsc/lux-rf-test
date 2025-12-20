"""
Terminal log 解析得到 TermGNSSRecord
NEMA log 解析得到 NMEARecord
需要转换成 GNSSRecord 进行统计分析
TODO 缺少方法将 TermGNSSRecord 转换成 GNSSRecord
"""
import re
from datetime import datetime, time as dt_time
from typing import Literal, Sequence, Optional, TypedDict

import pynmea2

from src.utils.logger import get_logger

logger = get_logger()

AllowedMode = Literal["gps", "bds", "gal", "gln"]
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
    '''
    "gsv_infos": {"gps_gsv": [gps_nmea_sat1, gps_nmea_sat2, ...], "glo_gsv": [glo_nmea_sat1, glo_nmea_sat2, ...],
    "gal_gsv": [gal_nmea_sat1, gal_nmea_sat2, ...], "bds_gsv": [bds_nmea_sat1, bds_nmea_sat2, ...]}
    '''


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
    '''
    "overall": {"top4_cn": float, "sats": [top4_sat1, top4_sat2, top4_sat3, top4_sat4]},
    "gps_gsv": {"top4_cn": float, "sats": [top4_gps_sat1, top4_gps_sat2, top4_gps_sat3, top4_gps_sat4]},
    "bds_gsv": {"top4_cn": float, "sats": [top4_bds_sat1, top4_bds_sat2, top4_bds_sat3, top4_bds_sat4]},
    "gal_gsv": {"top4_cn": float, "sats": [top4_gal_sat1, top4_gal_sat2, top4_gal_sat3, top4_gal_sat4]},
    "gln_gsv": {"top4_cn": float, "sats": [top4_gln_sat1, top4_gln_sat2, top4_gln_sat3, top4_gln_sat4]}}
    '''


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
    从 terminal log 中提取 gnss 信息
    :param log_text:
    :param gnss_modes: 指定星座，默认全部选中
    :param block_num: 指定第 block_num 个 gnss info block
    :param positive_ttff: 如果为 True 只抓取 ttff > 0
    :param start_marker: 如果为空则从 text 开头开始，否则从 start_marker 之后开始解析
    :param end_marker: 如果为空则到 text 结束截止，否则解析到 end_marker 截止
    :param start_delay: 从 start_maker 开始延迟 start_delay 个数据开始记录
    :return: term_gnss_data = [term_gnss_record1, term_gnss_record2, ... ]

             term_gnss_record = {"utc_time": str, "start": str, "top4_cn": float, "pos_sta": str, "pos_ttff": int,
             "use_num": int, "total_sv_num": int,
             "gps_gsv": [gps_term_sat1, gps_term_sat2, ...], "bds_gsv": [bds_term_sat1, bds_term_sat2, ...],
             "gal_gsv": [gal_term_sat1, gal_term_sat2, ...], "gln_gsv": [gln_term_sat1, gln_term_sat2, ...]}

             term_sat: (prn, cn)  prn: str, cn: float
    """
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

    :param log_text:
    :param gnss_modes: 指定星座，默认全部选中
    :return: nmea_data = [nmea_record1, nmea_record1, ...]

    nmea_record = {"utc_time": datetime.time, "latitude": float, "longitude": float, "altitude": float, "datetime": datetime.datetime,
    "speed_kph": float, "course": float, "num_sats": int, "hdop": float, "pdop": float, "vdop": float, "status": str}
    "gsv_infos": {"gps_gsv": [gps_nmea_sat1, gps_nmea_sat2, ...], "glo_gsv": [glo_nmea_sat1, glo_nmea_sat2, ...],
    "gal_gsv": [gal_nmea_sat1, gal_nmea_sat2, ...], "bds_gsv": [bds_nmea_sat1, bds_nmea_sat2, ...]}

    nmea_sat = {"prn": str, "elev": int, "azimuth": int, "snr": float}
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

        if not line.startswith('$') or line.startswith('$PAIRACC'):
            continue

        try:
            msg = pynmea2.parse(line)
        except pynmea2.ParseError:
            continue

        msg_time = getattr(msg, 'timestamp', None)  # 每一条信息都尝试提取timestamp属性
        if msg_time is not None:
            time_str = str(msg_time)
            if time_str != current_time_str:
                if current_record is not None:
                    nmea_data.append(current_record)
                current_time_str = time_str
                current_record = create_empty_record(msg_time)
        # $GNGGA 提供latitude（纬度）、longitude（经度）、altitude（海拔）、satellites（可见卫星数量）、hdop（Horizontal Dilution of Precision 水平精度因子）
        # $PAIRACC 是芯片厂商自定义协议，忽略
        # $GNGLL 未使用
        # $GNGSA 4条信息，每个星座对应1条。提供pdop（Position Dilution of Precision 位置几何精度因子）、hdop、vdop（Vertical Dilution of Precision 垂直精度因子）
        # $G#GSV 提供每颗卫星对应的prn（Pseudo-Random Noise 伪随机噪声）、elev（Elevation 俯仰角）、azimuth（Azimuth 方位角）、snr
        # $GNRMC 提供datetime、speed_kph、course（航向角）、status
        # $GNVTG 未使用
        # $GNZDA 未使用
        if current_record is None:
            continue

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
    计算top4 cn
    :param sats: [sat1, sat2, ...]
    sat = {"prn": int, "snr": float, **args}
    :param include_constellation: 是否包含 "constellation" key
    :return: (top4_cn，[top4_sat1, top4_sat2, top4_sat3, top4_sat4])
    """
    valid_sats = [s for s in sats if s.get('snr') is not None]
    if not valid_sats:
        return None, []

    top4_sats = sorted(valid_sats, key=lambda x: x['snr'], reverse=True)[:4]
    top4_cn = round(sum(s['snr'] for s in top4_sats) / 4, 2)

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

    :param nmea_data:
    :param gnss_modes:
    :return: gnss_infos = [gnss_time_dict1, gnss_time_dict2, ...]

    gnss_time_dict = {"utc_time": str（格式化为 HH:MM:SS）, "status": str,
    "overall": {"top4_cn": float, "sats": [top4_sat1, top4_sat2, top4_sat3, top4_sat4]},
    "gps_gsv": {"top4_cn": float, "sats": [top4_gps_sat1, top4_gps_sat2, top4_gps_sat3, top4_gps_sat4]},
    "bds_gsv": {"top4_cn": float, "sats": [top4_bds_sat1, top4_bds_sat2, top4_bds_sat3, top4_bds_sat4]},
    "gal_gsv": {"top4_cn": float, "sats": [top4_gal_sat1, top4_gal_sat2, top4_gal_sat3, top4_gal_sat4]},
    "gln_gsv": {"top4_cn": float, "sats": [top4_gln_sat1, top4_gln_sat2, top4_gln_sat3, top4_gln_sat4]}}

    overall_sat = {"prn": str, "snr": float, "constellation": str}
    sat = {"prn": str, "snr": float}
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