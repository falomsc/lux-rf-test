class RFTestError(Exception):
    """RF测试基础异常"""
    pass


class InstrumentError(RFTestError):
    """仪表相关异常"""
    pass


class TestError(RFTestError):
    """测试执行异常"""
    pass


class ConnectionError(InstrumentError):
    """连接异常"""
    pass


class CommandError(InstrumentError):
    """命令执行异常"""
    pass


class ConfigError(RFTestError):
    """配置相关异常"""
    pass

class PosMaxAttemptError(RFTestError):
    """位置获取最大尝试次数异常"""
    pass


class RebootMaxAttemptError(RFTestError):
    """重启等待最大次数异常"""
    pass