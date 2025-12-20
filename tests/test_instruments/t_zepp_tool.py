# TODO 测试重写
from src.instruments.zepp_tool import ZeppTool
from src.utils.logger import setup_logger

setup_logger()
zt = ZeppTool("bdb12599")
zt.connect()
# zt.send_command("hm:gnss+proc=read_auto")
# zt.export_terminal_log()