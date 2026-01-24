import os
import sys
from datetime import time, timezone
from pathlib import Path

import pytest

from src.rf_tests.gnss.log_parser import calculate_top4_cn, parse_nmea_log

sys.path.append(os.getcwd())

@pytest.fixture()
def sample_nmea_log():
    current_dir = Path(__file__).parent
    log_file_path = current_dir / "data" / "nmea_sample.txt"
    if not log_file_path.exists():
        pytest.fail(f"NEMA测试数据文件未找到: {log_file_path}")
    with open(log_file_path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def sample_term_log():
    current_dir = Path(__file__).parent
    log_file_path = current_dir / "data" / "term_sample.txt"
    if not log_file_path.exists():
        pytest.fail(f"TERM测试数据文件未找到: {log_file_path}")
    with open(log_file_path, "r", encoding="utf-8") as f:
        return f.read()


def test_parse_terminal_gnss_log():
    """
    TODO 补充完整
    :return:
    """
    pass


def test_parse_nmea_log(sample_nmea_log):
    records = parse_nmea_log(sample_nmea_log)
    assert len(records) == 10

    rec1 = records[0]
    assert rec1["utc_time"] == time(6, 28, 58, tzinfo=timezone.utc)
    assert rec1["latitude"] > 0
    assert rec1["num_sats"] == 12
    assert rec1["hdop"] == 0.78
    gps_sats = rec1["gsv_infos"]["gps_gsv"]
    assert len(gps_sats) == 4
    assert gps_sats[0]["prn"] == "01"
    assert gps_sats[0]["snr"] == 36.5

    bds_sats = rec1["gsv_infos"]["bds_gsv"]
    assert len(bds_sats) == 3
    assert bds_sats[0]["snr"] == 36.4

    rec2 = records[1]
    assert rec2["utc_time"] == time(6, 28, 59, tzinfo=timezone.utc)
    assert rec2["speed_kph"] == 0


def test_calc_top4_cn():
    # 1，超过4颗星
    sats = [
        {"prn": "1", "snr": 10.0},
        {"prn": "2", "snr": 40.0},
        {"prn": "3", "snr": 30.0},
        {"prn": "4", "snr": 20.0},
        {"prn": "5", "snr": 50.0},
    ]
    cn, top_sats = calculate_top4_cn(sats)
    assert cn == 35.0
    assert len(top_sats) == 4
    assert top_sats[0]["prn"] == "5"  # 排序检查
    # 2，少于4颗星
    sats_few = [
        {"prn": "1", "snr": 40.0},
        {"prn": "2", "snr": 20.0}
    ]
    cn, top_sats = calculate_top4_cn(sats_few)
    assert cn == 15.0
    assert len(top_sats) == 2
    # 3，空列表
    cn, top_sats = calculate_top4_cn([])
    assert cn is None
    assert top_sats == []
    # 4，包含constellation字段
    sats_const = [{"prn": "1", "snr": 40.0, "constellation": "gps"}]
    cn, top_sats = calculate_top4_cn(sats_const, include_constellation=True)
    assert top_sats[0]["constellation"] == "gps"


def test_convert_nmea_to_gnss_info():
    """
    TODO 待补充
    :return:
    """
    pass