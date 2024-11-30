import asyncio

import pytest
import pytest_asyncio
from aioresponses import aioresponses

from app.api_client import CRCONApiClient
from app.crcon_server_details import CRCONServerDetails


def describe_when_not_entered():
    """
    Tests of behaviour when the client context manager is not entered correctly.
    """

    @pytest_asyncio.fixture(loop_scope="function")
    async def current_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    @pytest.fixture()
    def sut(current_loop: asyncio.AbstractEventLoop) -> CRCONApiClient:
        server_details = CRCONServerDetails(api_base_url="https://my.example.com", api_key="1234567890")
        return CRCONApiClient(server_details=server_details, loop=current_loop)

    @pytest.mark.asyncio()
    async def get_status_raises_exception(sut: CRCONApiClient):
        with pytest.raises(RuntimeError) as exc:
            await sut.get_status()

        assert str(exc.value) == "CRCONApiClient context must be entered"


def describe_when_entered():
    """
    Tests of behaviour when the client context manager is entered correctly.
    """

    DEFAULT_RESULT = {
        "result": {
            "name": "My Server",
            "map": {
                "id": "remagen_warfare",
                "map": {
                    "id": "remagen",
                    "name": "REMAGEN",
                    "tag": "REM",
                    "pretty_name": "Remagen",
                    "shortname": "Remagen",
                    "allies": {"name": "us", "team": "allies"},
                    "axis": {"name": "ger", "team": "axis"},
                    "orientation": "vertical",
                },
                "game_mode": "warfare",
                "attackers": None,
                "environment": "day",
                "pretty_name": "Remagen Warfare",
                "image_name": "remagen-day.webp",
            },
            "current_players": 96,
            "max_players": 100,
            "short_name": "My Server",
            "server_number": 1,
        },
        "command": "get_status",
        "arguments": {},
        "failed": False,
        "error": None,
        "forward_results": None,
        "version": "v10.6.0",
    }

    @pytest_asyncio.fixture()
    async def mock_response():
        with aioresponses() as mocker:
            yield mocker

    @pytest_asyncio.fixture()
    async def current_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    @pytest_asyncio.fixture()
    async def sut(current_loop: asyncio.AbstractEventLoop):
        server_details = CRCONServerDetails(api_base_url="https://my.example.com", api_key="1234567890")
        async with CRCONApiClient(server_details=server_details, loop=current_loop) as sut:
            yield sut

    @pytest.mark.asyncio()
    async def get_status_succeeds(sut: CRCONApiClient, mock_response: aioresponses):
        # ***** ARRANGE *****

        url = "https://my.example.com/api/get_status"
        mock_response.get(url, status=200, payload=DEFAULT_RESULT)

        # ***** ACT *****
        result = await sut.get_status()

        # ***** ASSERT *****
        assert result.current_players == 96

    @pytest.mark.asyncio()
    async def get_status_retries_on_failure(sut: CRCONApiClient, mock_response: aioresponses):
        # ***** ARRANGE *****

        url = "https://my.example.com/api/get_status"
        mock_response.get(url, status=500)
        mock_response.get(url, status=200, payload=DEFAULT_RESULT)

        # ***** ACT *****
        result = await sut.get_status()

        # ***** ASSERT *****
        assert result.current_players == 96
