"""
Steam Automation Hub - 库存管理模块
实现 Steam 库存同步、物品追踪、价格监控
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from .steam_client import SteamClient

logger = logging.getLogger(__name__)


class ItemQuality(Enum):
    """物品品质"""
    CONSUMER = "consumer_grade"
    INDUSTRIAL = "industrial_grade"
    MIL_SPEC = "mil_spec"
    RESTRICTED = "restricted"
    CLASSIFIED = "classified"
    COVERT = "covert"
    CONTRABAND = "contraband"


class ItemType(Enum):
    """物品类型"""
    WEAPON = "weapon"
    KNIFE = "knife"
    GLOVES = "gloves"
    STICKER = "sticker"
    GRAFFITI = "graffiti"
    CASE = "case"
    KEY = "key"
    MUSIC_KIT = "music_kit"
    AGENT = "agent"
    OTHER = "other"


@dataclass
class InventoryItem:
    """库存物品"""
    asset_id: str
    class_id: str
    instance_id: str
    market_hash_name: str
    market_name: str
    name_color: str = ""
    quality: str = ""
    item_type: str = ""
    tradable: bool = True
    marketable: bool = True
    amount: int = 1
    icon_url: str = ""
    descriptions: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    actions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "market_hash_name": self.market_hash_name,
            "market_name": self.market_name,
            "tradable": self.tradable,
            "marketable": self.marketable,
            "quality": self.quality,
        }


@dataclass
class InventorySnapshot:
    """库存快照"""
    app_id: int
    context_id: int
    items: list[InventoryItem] = field(default_factory=list)
    total_count: int = 0
    timestamp: float = 0.0

    @property
    def tradable_count(self) -> int:
        return sum(1 for item in self.items if item.tradable)

    @property
    def marketable_count(self) -> int:
        return sum(1 for item in self.items if item.marketable)


class InventoryManager:
    """Steam 库存管理器

    功能:
    - 多游戏库存同步（CS2/Dota2/TF2）
    - 库存变更检测与通知
    - 物品分类与统计
    - 价格查询
    """

    # 支持的游戏
    SUPPORTED_APPS = {
        730: "CS2",
        570: "Dota 2",
        440: "Team Fortress 2",
        753: "Steam Items",
        252490: "Rust",
    }

    def __init__(self, client: SteamClient):
        self.client = client
        self._inventories: dict[int, InventorySnapshot] = {}
        self._on_change: Optional[Callable] = None
        self._price_cache: dict[str, float] = {}

    def set_change_callback(self, callback: Callable):
        """设置库存变更回调

        Args:
            callback: 回调函数 callback(app_id, added_items, removed_items)
        """
        self._on_change = callback

    async def sync_inventory(self, app_id: int = 730,
                              context_id: int = 2) -> InventorySnapshot:
        """同步库存

        Args:
            app_id: 游戏 App ID
            context_id: 库存上下文

        Returns:
            InventorySnapshot: 库存快照
        """
        import time

        game_name = self.SUPPORTED_APPS.get(app_id, f"App {app_id}")
        logger.info(f"🔄 正在同步库存: {game_name} (app_id={app_id})")

        raw_items = self.client.get_inventory(app_id, context_id)
        items = [self._parse_item(item) for item in raw_items]

        new_snapshot = InventorySnapshot(
            app_id=app_id,
            context_id=context_id,
            items=items,
            total_count=len(items),
            timestamp=time.time(),
        )

        # 检测变更
        if app_id in self._inventories:
            old_snapshot = self._inventories[app_id]
            added, removed = self._diff_inventory(old_snapshot, new_snapshot)

            if added or removed:
                logger.info(
                    f"库存变更: +{len(added)} -{len(removed)} "
                    f"({game_name})"
                )
                if self._on_change:
                    self._on_change(app_id, added, removed)

        self._inventories[app_id] = new_snapshot
        logger.info(
            f"✅ 库存同步完成: {game_name}, "
            f"总计 {new_snapshot.total_count} 件, "
            f"可交易 {new_snapshot.tradable_count} 件"
        )

        return new_snapshot

    async def sync_all(self) -> dict[int, InventorySnapshot]:
        """同步所有游戏库存"""
        results = {}
        for app_id in self.SUPPORTED_APPS:
            try:
                snapshot = await self.sync_inventory(app_id)
                results[app_id] = snapshot
            except Exception as e:
                logger.error(f"同步库存失败 {app_id}: {e}")
        return results

    def _parse_item(self, raw_item: dict) -> InventoryItem:
        """解析原始物品数据"""
        descriptions = raw_item.get("descriptions", [])
        tags = raw_item.get("tags", [])

        # 提取品质
        quality = ""
        for desc in descriptions:
            if "Exterior" in desc.get("value", "") or "Grade" in desc.get("value", ""):
                quality = desc.get("value", "")
                break

        # 提取类型
        item_type = "other"
        for tag in tags:
            category = tag.get("category", "")
            if category == "Type":
                item_type = tag.get("internal_name", "other")

        return InventoryItem(
            asset_id=raw_item.get("assetid", ""),
            class_id=raw_item.get("classid", ""),
            instance_id=raw_item.get("instanceid", ""),
            market_hash_name=raw_item.get("market_hash_name", ""),
            market_name=raw_item.get("name", ""),
            name_color=raw_item.get("name_color", ""),
            quality=quality,
            item_type=item_type,
            tradable=raw_item.get("tradable", 0) == 1,
            marketable=raw_item.get("marketable", 0) == 1,
            amount=int(raw_item.get("amount", 1)),
            icon_url=raw_item.get("icon_url", ""),
            descriptions=descriptions,
            tags=tags,
        )

    def _diff_inventory(self, old: InventorySnapshot,
                         new: InventorySnapshot) -> tuple[list, list]:
        """计算库存差异

        Args:
            old: 旧快照
            new: 新快照

        Returns:
            tuple: (新增物品列表, 移除物品列表)
        """
        old_ids = {item.asset_id for item in old.items}
        new_ids = {item.asset_id for item in new.items}

        added_ids = new_ids - old_ids
        removed_ids = old_ids - new_ids

        added = [item for item in new.items if item.asset_id in added_ids]
        removed = [item for item in old.items if item.asset_id in removed_ids]

        return added, removed

    def get_inventory_snapshot(self, app_id: int = 730) -> Optional[InventorySnapshot]:
        """获取库存快照"""
        return self._inventories.get(app_id)

    def get_total_value(self, app_id: int = 730) -> float:
        """估算库存总价值"""
        snapshot = self._inventories.get(app_id)
        if not snapshot:
            return 0.0
        # 简化计算：可交易物品数 * 均价
        return snapshot.tradable_count * self._average_price(app_id)

    def _average_price(self, app_id: int) -> float:
        """获取平均价格（占位）"""
        return 1.0

    def get_items_by_quality(self, app_id: int = 730,
                              quality: str = "") -> list[InventoryItem]:
        """按品质筛选物品"""
        snapshot = self._inventories.get(app_id)
        if not snapshot:
            return []
        if not quality:
            return snapshot.items
        return [item for item in snapshot.items if item.quality == quality]

    def get_items_by_type(self, app_id: int = 730,
                           item_type: str = "") -> list[InventoryItem]:
        """按类型筛选物品"""
        snapshot = self._inventories.get(app_id)
        if not snapshot:
            return []
        if not item_type:
            return snapshot.items
        return [item for item in snapshot.items if item.item_type == item_type]

    def search_items(self, keyword: str, app_id: int = 730) -> list[InventoryItem]:
        """搜索库存物品"""
        snapshot = self._inventories.get(app_id)
        if not snapshot:
            return []
        keyword_lower = keyword.lower()
        return [
            item for item in snapshot.items
            if keyword_lower in item.market_name.lower()
            or keyword_lower in item.market_hash_name.lower()
        ]

    def get_stats(self, app_id: int = 730) -> dict:
        """获取库存统计"""
        snapshot = self._inventories.get(app_id)
        if not snapshot:
            return {"error": "无库存数据"}

        type_distribution = {}
        quality_distribution = {}
        for item in snapshot.items:
            type_distribution[item.item_type] = \
                type_distribution.get(item.item_type, 0) + 1
            if item.quality:
                quality_distribution[item.quality] = \
                    quality_distribution.get(item.quality, 0) + 1

        return {
            "game": self.SUPPORTED_APPS.get(app_id, f"App {app_id}"),
            "total_items": snapshot.total_count,
            "tradable_items": snapshot.tradable_count,
            "marketable_items": snapshot.marketable_count,
            "type_distribution": type_distribution,
            "quality_distribution": quality_distribution,
            "last_sync": snapshot.timestamp,
        }
