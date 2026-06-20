"""
Steam Automation Hub - 消息监控模块
实现 Steam 消息的实时监控、自动回复与通知
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Pattern

from .steam_client import SteamClient

logger = logging.getLogger(__name__)


@dataclass
class MessageRule:
    """消息规则"""
    name: str
    pattern: str  # 正则模式
    response: str  # 自动回复模板
    case_sensitive: bool = False
    enabled: bool = True

    def __post_init__(self):
        flags = 0 if self.case_sensitive else re.IGNORECASE
        self._compiled: Pattern = re.compile(self.pattern, flags)

    def match(self, text: str) -> bool:
        """检查消息是否匹配规则"""
        return bool(self._compiled.search(text))


@dataclass
class IncomingMessage:
    """收件消息"""
    steam_id: str
    sender_name: str
    content: str
    timestamp: float
    room_id: Optional[str] = None

    @property
    def time_str(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class MonitorStats:
    """监控统计"""
    messages_received: int = 0
    messages_sent: int = 0
    rules_matched: int = 0
    start_time: float = 0.0
    last_message_time: float = 0.0

    @property
    def uptime_hours(self) -> float:
        import time
        if self.start_time == 0:
            return 0
        return (time.time() - self.start_time) / 3600


class MessageMonitor:
    """Steam 消息监控器

    功能:
    - 实时接收 Steam 消息
    - 基于正则规则的自动回复
    - 消息日志持久化
    - Webhook 通知推送
    - 关键词告警
    """

    def __init__(self, client: SteamClient, webhook_url: str = ""):
        self.client = client
        self.webhook_url = webhook_url
        self.rules: list[MessageRule] = []
        self.stats = MonitorStats()
        self._running = False
        self._message_history: list[IncomingMessage] = []
        self._max_history = 1000
        self._notify_callback: Optional[Callable] = None

    def add_rule(self, name: str, pattern: str, response: str,
                 case_sensitive: bool = False) -> None:
        """添加自动回复规则

        Args:
            name: 规则名称
            pattern: 匹配模式（正则表达式）
            response: 自动回复内容
            case_sensitive: 是否区分大小写

        Examples:
            >>> monitor.add_rule(
            ...     "price_check",
            ...     r"how much.*knife",
            ...     "Please check the market for current prices!"
            ... )
        """
        rule = MessageRule(
            name=name,
            pattern=pattern,
            response=response,
            case_sensitive=case_sensitive,
        )
        self.rules.append(rule)
        logger.info(f"已添加规则: {name} -> {pattern}")

    def remove_rule(self, name: str) -> bool:
        """移除规则"""
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.name != name]
        removed = before > len(self.rules)
        if removed:
            logger.info(f"已移除规则: {name}")
        return removed

    def list_rules(self) -> list[dict]:
        """列出所有规则"""
        return [
            {
                "name": r.name,
                "pattern": r.pattern,
                "response": r.response,
                "enabled": r.enabled,
            }
            for r in self.rules
        ]

    def set_notification_callback(self, callback: Callable):
        """设置通知回调函数"""
        self._notify_callback = callback

    async def start(self):
        """启动消息监控"""
        import time
        self._running = True
        self.stats.start_time = time.time()

        logger.info("🟢 Steam 消息监控已启动")
        logger.info(f"已加载 {len(self.rules)} 条自动回复规则")

        self.client.set_message_callback(self._on_message_received)

    async def stop(self):
        """停止消息监控"""
        self._running = False
        logger.info("🔴 Steam 消息监控已停止")
        logger.info(f"运行统计: {self._format_stats()}")

    def _on_message_received(self, sender_id: str, message: str,
                              sender_name: str = "Unknown"):
        """消息接收回调"""
        import time

        msg = IncomingMessage(
            steam_id=sender_id,
            sender_name=sender_name,
            content=message,
            timestamp=time.time(),
        )

        self._message_history.append(msg)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]

        self.stats.messages_received += 1
        self.stats.last_message_time = msg.timestamp

        logger.info(f"📨 [{msg.time_str}] {sender_name}: {message[:100]}")

        # 规则匹配
        matched_rules = [r for r in self.rules if r.enabled and r.match(message)]

        for rule in matched_rules:
            self.stats.rules_matched += 1
            response = rule.response.format(
                sender=sender_name,
                message=message,
                time=msg.time_str,
            )
            logger.info(f"🔧 规则匹配: {rule.name} -> {response[:50]}...")
            self.client.send_message(sender_id, response)
            self.stats.messages_sent += 1

    async def send_notification(self, message: str):
        """发送 Webhook 通知

        Args:
            message: 通知内容
        """
        if not self.webhook_url:
            return

        try:
            import urllib.request
            import json

            payload = json.dumps({
                "msgtype": "text",
                "text": {
                    "content": f"🔔 [Steam Monitor]\n{message}"
                }
            }).encode("utf-8")

            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            logger.debug("Webhook 通知已发送")
        except Exception as e:
            logger.error(f"Webhook 发送失败: {e}")

    def get_recent_messages(self, count: int = 20) -> list[IncomingMessage]:
        """获取最近的消息"""
        return self._message_history[-count:]

    def search_messages(self, keyword: str) -> list[IncomingMessage]:
        """搜索消息历史

        Args:
            keyword: 搜索关键词

        Returns:
            list: 匹配的消息列表
        """
        keyword_lower = keyword.lower()
        return [
            msg for msg in self._message_history
            if keyword_lower in msg.content.lower()
            or keyword_lower in msg.sender_name.lower()
        ]

    def get_message_count(self, steam_id: Optional[str] = None) -> int:
        """获取消息计数"""
        if steam_id:
            return sum(1 for m in self._message_history if m.steam_id == steam_id)
        return len(self._message_history)

    def _format_stats(self) -> str:
        """格式化统计信息"""
        return (
            f"接收消息: {self.stats.messages_received}, "
            f"发送回复: {self.stats.messages_sent}, "
            f"规则命中: {self.stats.rules_matched}, "
            f"运行时间: {self.stats.uptime_hours:.1f}h"
        )
