import datetime as dt
from unittest.mock import AsyncMock

import pytest

from crcon.api_client import ApiClient
from polebot.services.vip_manager import VipManager


@pytest.fixture
def standard_vip_list() -> str:
    return """76561198215199999 Joe Random 1 2025-11-09T12:04:55+00:00
76561198215199998 Joe Random 2 2025-04-07T17:03:29+00:00
76561198215199997 Joe Random 3 2025-01-01T00:00:00+00:00
4e44b6b62cea45e18f356105dcf00a03 Joe Random 4 2025-07-21T14:43:43+00:00
76561198215199995 Joe Random 5 3000-01-01T00:00:00+00:00
76561198215199994 Joe Random 6 2025-03-23T11:21:11+00:00
76561198215199993 Joe Random 7 2025-09-02T23:05:17+00:00
76561198215199992 Joe Random 8 2025-08-26T21:44:28+00:00
76561198215199991 Joe Random 9 2025-06-01T13:57:15+00:00"""

@pytest.fixture
def standard_api_client(standard_vip_list: str) -> AsyncMock:
    return mock_api_client(standard_vip_list)


def when_vip_list_is_not_empty():

    @pytest.mark.asyncio
    async def can_get_player_by_name(standard_api_client: ApiClient):
        sut = VipManager(standard_api_client)
        result = await sut.get_vip_by_name_or_id("Joe Random 1")
        assert result.player_id == "76561198215199999"
        assert result.player_name == "Joe Random 1"
        assert result.vip_expiry == dt.datetime(2025, 11, 9, hour=12, minute=4, second=55, tzinfo=dt.UTC)

    @pytest.mark.asyncio
    async def can_get_player_by_id(standard_api_client: ApiClient):
        sut = VipManager(standard_api_client)
        result = await sut.get_vip_by_name_or_id("76561198215199992")
        assert result.player_id == "76561198215199992"
        assert result.player_name == "Joe Random 8"
        assert result.vip_expiry == dt.datetime(2025, 8, 26, 21, minute=44, second=28, tzinfo=dt.UTC)

    @pytest.mark.asyncio
    async def returns_none_for_player_without_vip(standard_api_client: ApiClient):
        sut = VipManager(standard_api_client)
        result = await sut.get_vip_by_name_or_id("does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def player_with_permanent_vip_has_no_expiry(standard_api_client: ApiClient):
        sut = VipManager(standard_api_client)
        result = await sut.get_vip_by_name_or_id("Joe Random 5")
        assert result is not None
        assert result.vip_expiry is None


def mock_api_client(download_vip_list: str) -> AsyncMock:
    client = AsyncMock(spec=ApiClient)
    client.download_vips.return_value = download_vip_list
    return client
