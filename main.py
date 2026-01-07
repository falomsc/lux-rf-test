from tests.gnss.log_parser import parse_nmea_log, convert_nmea_to_gnss_info

with open('emmc.txt', 'r') as file:
    nmea_log = file.read()

gnss_modes = ('gps', 'bds', 'gln')
nmea_data = parse_nmea_log(nmea_log)
gnss_infos = convert_nmea_to_gnss_info(nmea_data)
overall_top4_cn_values = [
    info['overall']['top4_cn']
    for info in gnss_infos
    if info['overall']['top4_cn'] is not None
]
avg_value = sum(overall_top4_cn_values) / len(overall_top4_cn_values)
min_value = min(overall_top4_cn_values[:186])
print(avg_value)
print(min_value)