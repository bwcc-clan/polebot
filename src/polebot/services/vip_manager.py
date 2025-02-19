import datetime as dt
import logging
from typing import Any

import cachetools

from crcon.api_client import ApiClient
from polebot.models import VipInfo
from utils.cachetools import CacheItem, cache_item_ttu, ttl_cached

logger = logging.getLogger(__name__)


class VipManager:
    def __init__(self, api_client: ApiClient) -> None:
        self._api_client = api_client
        self._cache = cachetools.TLRUCache(maxsize=100, ttu=cache_item_ttu)

    async def get_vip_by_name_or_id(self, player_id_or_name: str) -> VipInfo | None:
        vip_list = await self._get_vip_list()
        return next((vip for vip in vip_list if _player_id_or_name_matches(player_id_or_name, vip)), None)

    def get_cache(self, cache_hint: str | None = None) -> cachetools.TLRUCache[Any, CacheItem[Any]]:
        """Get the cache for this instance."""
        return self._cache

    @ttl_cached(time_to_live=60)
    async def _get_vip_list(self) -> list[VipInfo]:
        logger.debug("Downloading VIP list")
        vip_list_doc = await self._api_client.download_vips()
        vip_list: list[VipInfo] = []
        for line in vip_list_doc.splitlines():
            try:
                vip_list.append(_parse_vip(line))
            except ValueError as ex:
                logger.error("Error parsing VIP info from %s", line, exc_info=ex)
        return vip_list


def _player_id_or_name_matches(player_id_or_name: str, vip: VipInfo) -> bool:
    return player_id_or_name in (vip.player_id, vip.player_name)


def _parse_vip(line: str) -> VipInfo:
    try:
        # Shitty format for VIP file puts the name in the middle. Names can contain spaces, so
        # we have to look for spaces from the start and the end to extract the info
        # e.g. 76561198215199999 Some Random Player 3000-01-01T00:00:00+00:00
        pos1 = line.find(" ")
        pos2 = line.rfind(" ")
        player_id = line[:pos1]
        name = line[pos1 + 1 : pos2]
        tmp = line[pos2 + 1 :]
        vip_expiry: dt.datetime | None = dt.datetime.fromisoformat(tmp)
        if vip_expiry and vip_expiry >= dt.datetime(2999, 12, 30, tzinfo=dt.UTC):
            vip_expiry = None
        vip = VipInfo(player_id, name, vip_expiry)
    except Exception as ex:
        raise ValueError("Error parsing VIP info: %s", ex) from ex
    else:
        return vip
