def format_duration(seconds: float) -> str:
    """
    把流逝过的秒转化成小时分钟秒
    """
    if seconds < 0:
        return "无效时间"

    total_seconds = round(seconds)

    if total_seconds < 60:
        return f"{total_seconds}秒"

    if total_seconds < 3600:
        minutes, secs = divmod(total_seconds, 60)
        return f"{minutes}分钟 {secs}秒"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}小时 {minutes}分钟 {secs}秒"