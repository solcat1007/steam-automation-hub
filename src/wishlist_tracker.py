"""
Steam Automation Hub - 愿望单追踪模块
监控 Steam 愿望单变动：降价、上新、下架、折扣提醒
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from .steam_client import SteamClient

logger = logging.getLogger(__name__)


class WishlistEvent(Enum):
    """愿望单事件类型"""
    PRICE_DROP = "price_drop"        # 降价
    ON_SALE = "on_sale"             # 折扣中
    SALE_ENDED = "sale_ended"       # 折扣结束
    RELEASED = "released"           # 已发布
    NEW_DLC = "new_dlc"             # 新 DLC
    REMOVED = "removed"             # 从愿望单移除
    PRICE_INCREASE = "price_increase"  # 涨价


@dataclass
class WishlistGame:
    """愿望单游戏"""
    app_id: int
    name: str
    capsule_url: str = ""
    release_date: str = ""
    is_released: bool = False
    is_free: bool = False
    # 价格信息
    original_price: float = 0.0  # 原价（分）
    current_price: float = 0.0   # 现价（分）
    discount_percent: int = 0     # 折扣百分比
    currency: str = "CNY"
    # 追踪信息
    rank: int = 0
    added_date: int = 0
    last_checked: int = 0
    # 订阅选项
    price_alert_threshold: float = 0.0  # 价格提醒阈值（分）
    notify_sale: bool = True
    notify_release: bool = True

    @property
    def current_price_yuan(self) -> float:
        return self.current_price / 100.0

    @property
    def original_price_yuan(self) -> float:
        return self.original_price / 100.0

    @property
    def is_on_sale(self) -> bool:
        return self.discount_percent > 0

    @property
    def savings_yuan(self) -> float:
        if self.original_price > self.current_price:
            return (self.original_price - self.current_price) / 100.0
        return 0.0


@dataclass
class WishlistChange:
    """愿望单变动"""
    game: WishlistGame
    event: WishlistEvent
    old_value: Optional[float] = None  # 旧值（价格等）
    new_value: Optional[float] = None  # 新值
    timestamp: int = 0


class WishlistTracker:
    """愿望单追踪器

    功能:
    - Steam 愿望单同步
    - 价格变动监控
    - 折扣实时通知
    - 新品发布提醒
    - 多账号愿望单对比
    """

    def __init__(self, client: SteamClient, webhook_url: str = ""):
        self.client = client
        self.webhook_url = webhook_url
        self._wishlist: dict[int, WishlistGame] = {}
        self._change_history: list[WishlistChange] = []
        self._on_change: Optional[Callable] = None
        self._steam_id: Optional[str] = None

    def set_change_callback(self, callback: Callable):
        """设置变更回调"""
        self._on_change = callback

    async def sync_wishlist(self) -> list[WishlistGame]:
        """同步愿望单

        Returns:
            list[WishlistGame]: 当前愿望单列表
        """
        steam_id = self._steam_id or self.client.steam_id
        if not steam_id:
            logger.error("无法获取愿望单: Steam ID 未知")
            return []

        logger.info(f"🔄 正在同步愿望单: Steam ID = {steam_id}")

        raw_wishlist = self.client.get_wishlist(steam_id)
        if not raw_wishlist:
            logger.warning("愿望单为空或获取失败")
            return []

        # 解析愿望单项
        new_wishlist = {}
        changes = []

        for app_id_str, data in raw_wishlist.items():
            app_id = int(app_id_str)
            game = self._parse_wishlist_item(app_id, data)
            new_wishlist[app_id] = game

            # 检测变更
            if app_id in self._wishlist:
                old_game = self._wishlist[app_id]
                detected_changes = self._detect_changes(old_game, game)
                changes.extend(detected_changes)
            else:
                # 新加入愿望单
                changes.append(WishlistChange(
                    game=game,
                    event=WishlistEvent.ON_SALE if game.is_on_sale else WishlistEvent.NEW_DLC,
                    timestamp=game.last_checked,
                ))

        # 检测移除的游戏
        removed_app_ids = set(self._wishlist.keys()) - set(new_wishlist.keys())
        for app_id in removed_app_ids:
            old_game = self._wishlist[app_id]
            changes.append(WishlistChange(
                game=old_game,
                event=WishlistEvent.REMOVED,
                timestamp=old_game.last_checked,
            ))

        # 更新本地数据
        self._wishlist = new_wishlist
        self._change_history.extend(changes)

        logger.info(
            f"✅ 愿望单同步完成: {len(new_wishlist)} 个游戏, "
            f"{len(changes)} 项变更, "
            f"{sum(1 for g in new_wishlist.values() if g.is_on_sale)} 个折扣中"
        )

        # 发送通知
        for change in changes:
            await self._notify_change(change)
            if self._on_change:
                self._on_change(change)

        return list(new_wishlist.values())

    def _parse_wishlist_item(self, app_id: int, data: dict) -> WishlistGame:
        """解析愿望单数据"""
        import time

        subs = data.get("subs", [])
        price_data = subs[0] if subs else {}

        return WishlistGame(
            app_id=app_id,
            name=data.get("name", f"App {app_id}"),
            capsule_url=data.get("capsule", ""),
            release_date=data.get("release_string", ""),
            is_released=data.get("is_released", False),
            is_free=data.get("is_free", False),
            original_price=price_data.get("original_price", 0),
            current_price=price_data.get("price", 0),
            discount_percent=price_data.get("discount_pct", 0),
            rank=data.get("priority", 0),
            added_date=data.get("added", 0),
            last_checked=int(time.time()),
        )

    def _detect_changes(self, old: WishlistGame,
                         new: WishlistGame) -> list[WishlistChange]:
        """检测愿望单变动"""
        import time
        changes = []

        # 折扣开始
        if not old.is_on_sale and new.is_on_sale:
            changes.append(WishlistChange(
                game=new,
                event=WishlistEvent.ON_SALE,
                old_value=old.current_price,
                new_value=new.current_price,
                timestamp=int(time.time()),
            ))

        # 折扣结束
        elif old.is_on_sale and not new.is_on_sale:
            changes.append(WishlistChange(
                game=new,
                event=WishlistEvent.SALE_ENDED,
                old_value=old.current_price,
                new_value=new.current_price,
                timestamp=int(time.time()),
            ))

        # 降价（含更大折扣）
        elif old.current_price > new.current_price:
            changes.append(WishlistChange(
                game=new,
                event=WishlistEvent.PRICE_DROP,
                old_value=old.current_price,
                new_value=new.current_price,
                timestamp=int(time.time()),
            ))

        # 涨价
        elif old.current_price < new.current_price:
            changes.append(WishlistChange(
                game=new,
                event=WishlistEvent.PRICE_INCREASE,
                old_value=old.current_price,
                new_value=new.current_price,
                timestamp=int(time.time()),
            ))

        # 游戏发布
        if not old.is_released and new.is_released:
            changes.append(WishlistChange(
                game=new,
                event=WishlistEvent.RELEASED,
                timestamp=int(time.time()),
            ))

        return changes

    async def _notify_change(self, change: WishlistChange):
        """发送变动通知"""
        event_labels = {
            WishlistEvent.PRICE_DROP: "📉 降价",
            WishlistEvent.ON_SALE: "🏷️ 折扣中",
            WishlistEvent.SALE_ENDED: "⏹️ 折扣结束",
            WishlistEvent.RELEASED: "🎉 已发布",
            WishlistEvent.NEW_DLC: "📦 新 DLC",
            WishlistEvent.PRICE_INCREASE: "📈 涨价",
            WishlistEvent.REMOVED: "🗑️ 已移除",
        }

        label = event_labels.get(change.event, "更新")
        game = change.game

        msg_parts = [f"{label} | {game.name}"]

        if change.event in (WishlistEvent.PRICE_DROP, WishlistEvent.ON_SALE,
                            WishlistEvent.PRICE_INCREASE, WishlistEvent.SALE_ENDED):
            msg_parts.append(
                f"¥{game.current_price_yuan:.2f}"
                f"（原价 ¥{game.original_price_yuan:.2f}）"
            )
            if game.discount_percent > 0:
                msg_parts.append(f"-{game.discount_percent}%")

        message = " ".join(msg_parts)
        logger.info(f"🔔 {message}")

        # Webhook 通知
        if self.webhook_url:
            try:
                import urllib.request
                import json

                payload = json.dumps({
                    "msgtype": "text",
                    "text": {"content": f"🔔 [Wishlist]\n{message}"}
                }).encode("utf-8")

                req = urllib.request.Request(
                    self.webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                logger.error(f"愿望单通知发送失败: {e}")

    def get_wishlist(self) -> list[WishlistGame]:
        """获取当前愿望单"""
        return list(self._wishlist.values())

    def get_on_sale(self, min_discount: int = 0) -> list[WishlistGame]:
        """获取折扣中的游戏

        Args:
            min_discount: 最低折扣百分比（0-100）

        Returns:
            list[WishlistGame]: 折扣游戏列表
        """
        return [
            g for g in self._wishlist.values()
            if g.is_on_sale and g.discount_percent >= min_discount
        ]

    def get_cheapest(self, limit: int = 10) -> list[WishlistGame]:
        """获取最便宜的游戏

        Args:
            limit: 返回数量

        Returns:
            list[WishlistGame]: 按价格升序排列
        """
        non_free = [g for g in self._wishlist.values() if not g.is_free and g.current_price > 0]
        return sorted(non_free, key=lambda g: g.current_price)[:limit]

    def get_best_deals(self, limit: int = 10) -> list[WishlistGame]:
        """获取最佳折扣

        Args:
            limit: 返回数量

        Returns:
            list[WishlistGame]: 按折扣百分比降序排列
        """
        on_sale = self.get_on_sale()
        return sorted(on_sale, key=lambda g: g.discount_percent, reverse=True)[:limit]

    def get_unreleased(self) -> list[WishlistGame]:
        """获取未发布的游戏"""
        return [g for g in self._wishlist.values() if not g.is_released]

    def search(self, keyword: str) -> list[WishlistGame]:
        """搜索愿望单游戏"""
        kw = keyword.lower()
        return [
            g for g in self._wishlist.values()
            if kw in g.name.lower()
        ]

    def get_total_value(self) -> float:
        """愿望单总价值（当前价格）"""
        return sum(g.current_price for g in self._wishlist.values() if not g.is_free) / 100.0

    def get_original_total_value(self) -> float:
        """愿望单总价值（原价）"""
        return sum(g.original_price for g in self._wishlist.values() if not g.is_free) / 100.0

    def get_stats(self) -> dict:
        """获取统计信息"""
        on_sale = self.get_on_sale()
        unreleased = self.get_unreleased()
        released = [g for g in self._wishlist.values() if g.is_released]

        return {
            "total": len(self._wishlist),
            "on_sale": len(on_sale),
            "unreleased": len(unreleased),
            "released": len(released),
            "current_total_value": f"¥{self.get_total_value():.2f}",
            "original_total_value": f"¥{self.get_original_total_value():.2f}",
            "potential_savings": f"¥{self.get_original_total_value() - self.get_total_value():.2f}",
            "changes_tracked": len(self._change_history),
        }
