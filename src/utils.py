"""
Steam Automation Hub - 工具函数模块
日志、配置加载、数据格式化、加密工具
"""

import logging
import logging.handlers
import os
import json
import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime


def setup_logging(level: str = "INFO", log_file: str = "",
                  console: bool = True) -> logging.Logger:
    """配置全局日志

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径
        console: 是否输出到控制台

    Returns:
        logging.Logger: 根日志记录器
    """
    logger = logging.getLogger("steam_hub")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console and not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)

    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载 YAML 配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        dict: 配置字典
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("请安装 PyYAML: pip install pyyaml")

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


def load_json_config(config_path: str) -> dict:
    """加载 JSON 配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        dict: 配置字典
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_price(price_cents: int, currency: str = "CNY") -> str:
    """格式化价格

    Args:
        price_cents: 价格（分）
        currency: 货币代码

    Returns:
        str: 格式化后的价格字符串
    """
    symbols = {"CNY": "¥", "USD": "$", "EUR": "€"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{price_cents / 100:.2f}"


def format_timestamp(ts: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化时间戳

    Args:
        ts: Unix 时间戳
        fmt: 格式字符串

    Returns:
        str: 格式化后的时间字符串
    """
    return datetime.fromtimestamp(ts).strftime(fmt)


def format_duration(seconds: float) -> str:
    """格式化时间间隔

    Args:
        seconds: 秒数

    Returns:
        str: 人类可读的时间间隔
    """
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        return f"{int(seconds / 60)}分{int(seconds % 60)}秒"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}小时{minutes}分"
    else:
        days = int(seconds / 86400)
        hours = int((seconds % 86400) / 3600)
        return f"{days}天{hours}小时"


def retry(max_retries: int = 3, delay: float = 1.0,
          backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避倍数
        exceptions: 需要重试的异常类型
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}): "
                            f"{e}, {current_delay}s 后重试..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        raise last_exception

        return wrapper
    return decorator


def safe_get(d: dict, *keys, default: Any = None) -> Any:
    """安全获取嵌套字典值

    Args:
        d: 字典
        *keys: 键路径
        default: 默认值

    Returns:
        Any: 获取的值或默认值
    """
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def chunk_list(lst: list, size: int) -> list[list]:
    """将列表拆分为固定大小的块

    Args:
        lst: 输入列表
        size: 每块大小

    Returns:
        list[list]: 分块列表
    """
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def truncate_text(text: str, max_length: int = 200,
                  suffix: str = "...") -> str:
    """截断文本

    Args:
        text: 输入文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def generate_trade_token(steam_id: str, partner_id: str) -> str:
    """生成交易链接 token

    Args:
        steam_id: 自己的 Steam ID
        partner_id: 对方的 Steam ID

    Returns:
        str: 交易 token
    """
    import hashlib
    import base64

    raw = f"{steam_id}:{partner_id}:{int(time.time())}"
    hash_bytes = hashlib.sha256(raw.encode()).digest()
    token = base64.urlsafe_b64encode(hash_bytes).decode().rstrip("=")[:16]
    return token


def validate_steam_id(steam_id: str) -> bool:
    """验证 Steam ID 格式

    Args:
        steam_id: Steam ID 字符串

    Returns:
        bool: 是否有效
    """
    if not steam_id:
        return False

    # Steam ID 64 (17位数字)
    if steam_id.startswith("7656") and len(steam_id) == 17 and steam_id.isdigit():
        return True

    # Steam ID 32 (STEAM_X:Y:ZZZZZZZZ)
    if steam_id.startswith("STEAM_"):
        parts = steam_id.split(":")
        return len(parts) == 3

    return False


def get_env_or_config(key: str, config: dict, default: Any = None) -> Any:
    """从环境变量或配置字典获取值（优先环境变量）

    Args:
        key: 键名
        config: 配置字典
        default: 默认值

    Returns:
        Any: 获取的值
    """
    env_value = os.environ.get(key.upper())
    if env_value is not None:
        return env_value

    return safe_get(config, *key.lower().split("."), default=default)
