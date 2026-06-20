"""
Steam Automation Hub - 腾讯云 SCF 入口函数
适配腾讯云云函数运行环境，实现 7×24 小时无人值守
"""

import os
import json
import logging
import asyncio

# 设置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 腾讯云 SCF 环境下，/tmp 是唯一可写目录
TMP_DIR = "/tmp"
DATA_DIR = os.path.join(TMP_DIR, "steam_hub_data")
os.makedirs(DATA_DIR, exist_ok=True)


def load_config_from_env():
    """从环境变量加载配置（SCF 环境）"""
    config = {
        "steam": {
            "username": os.environ.get("STEAM_USERNAME", ""),
            "password": os.environ.get("STEAM_PASSWORD", ""),
            "shared_secret": os.environ.get("STEAM_SHARED_SECRET", ""),
            "identity_secret": os.environ.get("STEAM_IDENTITY_SECRET", ""),
        },
        "tencent_cloud": {
            "secret_id": os.environ.get("TENCENT_SECRET_ID", ""),
            "secret_key": os.environ.get("TENCENT_SECRET_KEY", ""),
            "region": os.environ.get("TENCENT_REGION", "ap-guangzhou"),
        },
        "notifications": {
            "webhook_url": os.environ.get("WEBHOOK_URL", ""),
            "email": os.environ.get("NOTIFY_EMAIL", ""),
        },
        "logging": {
            "level": os.environ.get("LOG_LEVEL", "INFO"),
            "file": os.path.join(TMP_DIR, "steam_hub.log"),
        },
        "scf": {
            "sync_interval": int(os.environ.get("SYNC_INTERVAL", "300")),
            "max_execution_time": int(os.environ.get("SCF_TIMEOUT", "900")),
        },
    }
    return config


def main_handler(event, context):
    """腾讯云 SCF 主入口函数

    Args:
        event: SCF 触发事件
        context: SCF 运行上下文

    Returns:
        dict: 执行结果
    """
    logger.info("=" * 50)
    logger.info("🎮 Steam Automation Hub - SCF 模式启动")
    logger.info(f"Request ID: {context.request_id}")
    logger.info(f"剩余时间: {context.time_limit_in_ms}ms")
    logger.info("=" * 50)

    try:
        config = load_config_from_env()

        # 快速同步模式（SCF 有执行时间限制）
        result = asyncio.run(quick_sync(config, event, context))

        logger.info(f"✅ SCF 执行完成: {json.dumps(result, ensure_ascii=False)}")
        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False),
        }

    except Exception as e:
        logger.error(f"❌ SCF 执行异常: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}, ensure_ascii=False),
        }


async def quick_sync(config: dict, event: dict, context) -> dict:
    """快速同步（适配 SCF 超时限制）

    Returns:
        dict: 同步结果摘要
    """
    from src.steam_client import SteamClient, SteamConfig
    from src.message_monitor import MessageMonitor
    from src.inventory_manager import InventoryManager
    from src.trade_bot import TradeBot
    from src.wishlist_tracker import WishlistTracker

    steam_cfg = SteamConfig(
        username=config["steam"]["username"],
        password=config["steam"]["password"],
        shared_secret=config["steam"]["shared_secret"],
        identity_secret=config["steam"]["identity_secret"],
    )

    client = SteamClient(steam_cfg)
    webhook = config["notifications"]["webhook_url"]

    # 登录
    if not client.login():
        return {"error": "Steam 登录失败"}

    result = {
        "timestamp": context.request_id,
        "steam_id": client.steam_id,
        "modules": {},
    }

    try:
        # 消息监控 - 快速检查
        if config.get("message_monitor", {}).get("enabled", True):
            monitor = MessageMonitor(client, webhook)
            await monitor.start()
            result["modules"]["messages"] = {
                "status": "ok",
                "stats": monitor.stats.__dict__ if hasattr(monitor.stats, '__dict__') else {},
            }

        # 库存同步
        if config.get("inventory", {}).get("enabled", True):
            inventory = InventoryManager(client)
            snapshot = await inventory.sync_inventory(app_id=730)
            result["modules"]["inventory"] = inventory.get_stats(730)

        # 交易检查
        if config.get("trade_bot", {}).get("enabled", True):
            bot = TradeBot(client)
            active = client.get_trade_offers("active")
            result["modules"]["trades"] = {
                "active_offers": len(active) if active else 0,
            }

        # 愿望单同步
        if config.get("wishlist", {}).get("enabled", True):
            tracker = WishlistTracker(client, webhook)
            wishlist = await tracker.sync_wishlist()
            result["modules"]["wishlist"] = tracker.get_stats()

    except Exception as e:
        logger.error(f"模块执行异常: {e}")

    finally:
        client.logout()

    return result


def timer_handler(event, context):
    """定时触发器入口（cron 触发）"""
    logger.info("⏰ SCF 定时任务触发")
    return main_handler(event, context)


def api_gateway_handler(event, context):
    """API 网关触发器入口

    用于通过 HTTP 请求手动触发同步或查询状态
    """
    logger.info("🌐 API 网关触发")

    path = event.get("path", "/")
    method = event.get("httpMethod", "GET")

    if method == "GET" and path == "/status":
        return {
            "statusCode": 200,
            "body": json.dumps({
                "service": "Steam Automation Hub",
                "version": "1.0.0",
                "status": "running",
                "timestamp": event.get("requestContext", {}).get("requestTime", ""),
            }, ensure_ascii=False),
        }

    if method == "POST" and path == "/sync":
        return main_handler(event, context)

    return {
        "statusCode": 404,
        "body": json.dumps({"error": "Not Found"}, ensure_ascii=False),
    }
