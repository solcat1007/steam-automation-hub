"""
Steam Automation Hub
====================
基于腾讯云 SCF 的 Steam 全自动 AI 助手

覆盖消息监控、库存管理、交易机器人、愿望单追踪等核心场景
"""

import asyncio
import logging
import sys
from pathlib import Path

from .steam_client import SteamClient, SteamConfig
from .message_monitor import MessageMonitor, MessageRule
from .inventory_manager import InventoryManager
from .trade_bot import TradeBot, TradeRule, TradeAction
from .wishlist_tracker import WishlistTracker
from .utils import setup_logging, load_config

logger = logging.getLogger("steam_hub")

__version__ = "1.0.0"
__author__ = "沐晴"
__all__ = [
    "SteamClient", "SteamConfig",
    "MessageMonitor", "MessageRule",
    "InventoryManager",
    "TradeBot", "TradeRule", "TradeAction",
    "WishlistTracker",
    "setup_logging", "load_config",
    "SteamHub",
]


class SteamHub:
    """Steam 自动化中枢

    统一管理所有子模块的生命周期
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)
        self._setup_logging()

        # 初始化 Steam 客户端
        steam_cfg = SteamConfig(
            username=self.config.get("steam", {}).get("username", ""),
            password=self.config.get("steam", {}).get("password", ""),
            shared_secret=self.config.get("steam", {}).get("shared_secret", ""),
            identity_secret=self.config.get("steam", {}).get("identity_secret", ""),
        )
        self.client = SteamClient(steam_cfg)

        # 获取 Webhook URL
        webhook = self.config.get("notifications", {}).get("webhook_url", "")

        # 初始化子模块
        self.message_monitor = MessageMonitor(self.client, webhook)
        self.inventory_manager = InventoryManager(self.client)
        self.trade_bot = TradeBot(self.client)
        self.wishlist_tracker = WishlistTracker(self.client, webhook)

        self._running = False

    def _setup_logging(self):
        """配置日志"""
        log_config = self.config.get("logging", {})
        level = log_config.get("level", "INFO")
        log_file = log_config.get("file", "")
        setup_logging(level=level, log_file=log_file, console=True)

    async def start(self):
        """启动所有模块"""
        logger.info("=" * 50)
        logger.info("🎮 Steam Automation Hub v{} 启动中...", __version__)
        logger.info("=" * 50)

        self._running = True

        # 登录 Steam
        if not self.client.login():
            logger.error("Steam 登录失败，退出")
            return

        # 启动各个模块
        tasks = []

        if self.config.get("message_monitor", {}).get("enabled", True):
            task = asyncio.create_task(self.message_monitor.start())
            tasks.append(task)

        if self.config.get("trade_bot", {}).get("enabled", True):
            task = asyncio.create_task(self.trade_bot.start())
            tasks.append(task)

        # 初始同步
        logger.info("正在执行初始数据同步...")
        await self.inventory_manager.sync_all()
        await self.wishlist_tracker.sync_wishlist()

        logger.info("✅ 所有模块已启动，进入值守模式")
        logger.info("-" * 50)

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """优雅关闭"""
        logger.info("正在关闭所有模块...")
        self._running = False

        await self.message_monitor.stop()
        await self.trade_bot.stop()

        self.client.logout()
        logger.info("👋 Steam Automation Hub 已关闭")

    def run(self):
        """同步入口：运行主循环"""
        asyncio.run(self.start())


def main():
    """CLI 入口"""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.yaml"
    hub = SteamHub(config_path)
    hub.run()


if __name__ == "__main__":
    main()
