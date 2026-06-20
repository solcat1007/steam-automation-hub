"""
Steam Automation Hub - 交易机器人模块
自动化交易报价处理引擎，支持自定义策略与安全检查
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from .steam_client import SteamClient, SteamTradeOffer

logger = logging.getLogger(__name__)


class TradeAction(Enum):
    """交易动作"""
    ACCEPT = "accept"
    DECLINE = "decline"
    IGNORE = "ignore"
    REVIEW = "review"  # 需要人工审查


class TradeState(Enum):
    """交易状态"""
    ACTIVE = "active"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELED = "canceled"
    EXPIRED = "expired"
    COUNTERED = "countered"


@dataclass
class TradeRule:
    """交易规则"""
    name: str
    description: str = ""
    # 条件
    max_items_give: int = 999
    min_items_receive: int = 0
    whitelist_steam_ids: list[str] = field(default_factory=list)
    blacklist_steam_ids: list[str] = field(default_factory=list)
    # 自动响应
    auto_accept: bool = False
    auto_decline_empty: bool = False  # 空报价自动拒绝
    require_message: bool = False  # 要求附带留言
    # 物品过滤
    allowed_items: list[str] = field(default_factory=list)
    blocked_items: list[str] = field(default_factory=list)
    enabled: bool = True

    def evaluate(self, offer: SteamTradeOffer) -> TradeAction:
        """评估交易报价

        Args:
            offer: 交易报价

        Returns:
            TradeAction: 推荐动作
        """
        # 黑名单检查
        if offer.partner_steam_id in self.blacklist_steam_ids:
            logger.info(f"交易规则 {self.name}: 对方在黑名单中 -> DECLINE")
            return TradeAction.DECLINE

        # 空报价检查
        if self.auto_decline_empty and not offer.items_to_receive:
            logger.info(f"交易规则 {self.name}: 空报价 -> DECLINE")
            return TradeAction.DECLINE

        # 留言检查
        if self.require_message and not offer.message.strip():
            logger.info(f"交易规则 {self.name}: 无留言 -> DECLINE")
            return TradeAction.DECLINE

        # 白名单自动接受
        if offer.partner_steam_id in self.whitelist_steam_ids:
            logger.info(f"交易规则 {self.name}: 对方在白名单中 -> ACCEPT")
            return TradeAction.ACCEPT

        # 物品数量限制
        if len(offer.items_to_give) > self.max_items_give:
            logger.info(
                f"交易规则 {self.name}: 给出物品过多 "
                f"({len(offer.items_to_give)} > {self.max_items_give}) -> DECLINE"
            )
            return TradeAction.DECLINE

        if len(offer.items_to_receive) < self.min_items_receive:
            logger.info(
                f"交易规则 {self.name}: 收到物品不足 "
                f"({len(offer.items_to_receive)} < {self.min_items_receive}) -> DECLINE"
            )
            return TradeAction.DECLINE

        # 默认: 需要人工审查
        return TradeAction.REVIEW


@dataclass
class TradeStats:
    """交易统计"""
    offers_received: int = 0
    offers_accepted: int = 0
    offers_declined: int = 0
    offers_sent: int = 0
    total_items_received: int = 0
    total_items_given: int = 0

    @property
    def acceptance_rate(self) -> float:
        if self.offers_received == 0:
            return 0
        return self.offers_accepted / self.offers_received


class TradeBot:
    """Steam 交易机器人

    功能:
    - 自动检测入站交易报价
    - 基于规则引擎自动审批
    - 交易历史记录
    - 安全策略（白名单/黑名单/限额）
    - 物品价值评估
    """

    def __init__(self, client: SteamClient):
        self.client = client
        self.rules: list[TradeRule] = []
        self.stats = TradeStats()
        self._running = False
        self._trade_history: list[SteamTradeOffer] = []
        self._on_decision: Optional[Callable] = None

    def add_rule(self, rule: TradeRule):
        """添加交易规则

        Args:
            rule: 交易规则对象
        """
        self.rules.append(rule)
        logger.info(f"已添加交易规则: {rule.name}")

    def set_decision_callback(self, callback: Callable):
        """设置决策回调

        Args:
            callback: callback(offer, action)
        """
        self._on_decision = callback

    async def start(self):
        """启动交易机器人"""
        self._running = True
        logger.info("🤖 交易机器人已启动")
        logger.info(f"已加载 {len(self.rules)} 条交易规则")

        self.client.set_trade_callback(self._on_trade_offer)

    async def stop(self):
        """停止交易机器人"""
        self._running = False
        logger.info("🔴 交易机器人已停止")

    def _on_trade_offer(self, offer_data: dict):
        """交易报价回调"""
        offer = SteamTradeOffer(
            trade_id=offer_data.get("tradeofferid", ""),
            partner_steam_id=offer_data.get("accountid_other", ""),
            items_to_receive=offer_data.get("items_to_receive", []),
            items_to_give=offer_data.get("items_to_give", []),
            message=offer_data.get("message", ""),
        )

        self.stats.offers_received += 1
        logger.info(f"📥 收到新交易报价: {offer.trade_id}")

        # 规则评估
        action = self._evaluate_offer(offer)

        # 执行动作
        self._execute_action(offer, action)

    def _evaluate_offer(self, offer: SteamTradeOffer) -> TradeAction:
        """评估交易报价"""
        for rule in self.rules:
            if not rule.enabled:
                continue
            action = rule.evaluate(offer)
            if action != TradeAction.REVIEW:
                return action
        return TradeAction.REVIEW

    def _execute_action(self, offer: SteamTradeOffer, action: TradeAction):
        """执行交易动作"""
        logger.info(f"交易 {offer.trade_id}: 决策 -> {action.value}")

        if action == TradeAction.ACCEPT:
            success = self.client.accept_trade(offer.trade_id)
            if success:
                self.stats.offers_accepted += 1
                self.stats.total_items_received += len(offer.items_to_receive)
                self.stats.total_items_given += len(offer.items_to_give)
                logger.info(f"✅ 已接受交易: {offer.trade_id}")

        elif action == TradeAction.DECLINE:
            self.client.decline_trade(offer.trade_id)
            self.stats.offers_declined += 1
            logger.info(f"❌ 已拒绝交易: {offer.trade_id}")

        elif action == TradeAction.REVIEW:
            logger.info(f"👀 交易需人工审查: {offer.trade_id}")

        if self._on_decision:
            self._on_decision(offer, action)

    def send_trade_offer(self, partner_steam_id: str,
                          items: list[str], message: str = "",
                          token: str = "") -> Optional[str]:
        """发送交易报价

        Args:
            partner_steam_id: 对方 Steam ID
            items: 要发送的物品 ID 列表
            message: 留言
            token: 交易链接 token

        Returns:
            Optional[str]: 新报价 ID，失败返回 None
        """
        logger.info(f"📤 发送交易报价 -> {partner_steam_id}: {len(items)} 件物品")
        self.stats.offers_sent += 1

        # TODO: 实现交易发送逻辑
        trade_id = f"sent_{self.stats.offers_sent}"
        return trade_id

    def get_trade_history(self, limit: int = 50) -> list[SteamTradeOffer]:
        """获取交易历史"""
        return self._trade_history[-limit:]

    def get_stats(self) -> dict:
        """获取交易统计"""
        return {
            "offers_received": self.stats.offers_received,
            "offers_accepted": self.stats.offers_accepted,
            "offers_declined": self.stats.offers_declined,
            "offers_sent": self.stats.offers_sent,
            "acceptance_rate": f"{self.stats.acceptance_rate:.1%}",
            "items_received": self.stats.total_items_received,
            "items_given": self.stats.total_items_given,
            "active_rules": len([r for r in self.rules if r.enabled]),
        }

    async def run_forever(self, poll_interval: int = 30):
        """持续运行交易机器人

        Args:
            poll_interval: 轮询间隔（秒）
        """
        import asyncio
        logger.info("🤖 交易机器人开始持续运行")

        while self._running:
            try:
                active_offers = self.client.get_trade_offers("active")
                for offer_data in active_offers:
                    self._on_trade_offer(offer_data)
            except Exception as e:
                logger.error(f"交易轮询异常: {e}")

            await asyncio.sleep(poll_interval)
