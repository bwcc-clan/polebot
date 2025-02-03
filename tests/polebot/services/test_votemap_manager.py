import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from testutils import support_files_dir

from polebot.crcon.api_client import CRCONApiClient
from polebot.crcon.api_models import ApiResult, Layer, ServerStatus, VoteMapUserConfig
from polebot.models import (
    EnvironmentGroup,
    MapGroup,
    ServerCRCONDetails,
    ServerParameters,
    WeightingParameters,
)
from polebot.services import converters
from polebot.services.votemap_manager import VotemapManager

SUPPORT_FILES_DIR = support_files_dir(__file__)


@pytest.fixture
def standard_layers() -> list[Layer]:
    filepath = SUPPORT_FILES_DIR.joinpath("get_maps.json")
    with filepath.open() as f:
        contents = json.load(f)
    converter = converters.make_rcon_converter()
    result = converter.structure(contents, ApiResult[list[Layer]])
    assert result.result is not None
    return result.result


@pytest.fixture
def standard_layers_by_id(standard_layers: list[Layer]) -> dict[str, Layer]:
    return {layer.id: layer for layer in standard_layers}


@pytest.fixture
def standard_status(standard_layers_by_id: dict[str, Layer]) -> ServerStatus:
    current_map = "carentan_warfare"
    return ServerStatus(
        name="Test",
        map=standard_layers_by_id[current_map],
        current_players=2,
        max_players=2,
        short_name="TEST",
        server_number=1,
    )


@pytest.fixture
def queue():
    return asyncio.Queue()


@pytest.fixture
def standard_server_params() -> ServerParameters:
    crcon_details = ServerCRCONDetails(api_url="https://hll.example.com", api_key="dummy")
    weighting_params = WeightingParameters(
        groups={
            "Top": MapGroup(
                weight=100,
                repeat_decay=0.8,
                maps=["carentan", "omahabeach", "stmariedumont", "stmereeglise", "utahbeach"],
            ),
            "Mid": MapGroup(
                weight=80,
                repeat_decay=0.5,
                maps=["elsenbornridge", "foy", "hill400"],
            ),
        },
        environments={
            "Day": EnvironmentGroup(weight=100, repeat_decay=0.8, environments=["day", "dawn"]),
            "Night": EnvironmentGroup(weight=50, repeat_decay=0.1, environments=["night"]),
        },
    )
    return ServerParameters(server_name="Test", crcon_details=crcon_details, weighting_params=weighting_params)


@pytest.fixture
def standard_votemap_config() -> VoteMapUserConfig:
    return VoteMapUserConfig(num_warfare_options=6, num_offensive_options=2, num_skirmish_control_options=2)


@pytest.fixture
def standard_api_client(
    standard_status: ServerStatus,
    standard_layers: list[Layer],
    standard_votemap_config: VoteMapUserConfig,
) -> AsyncMock:
    return mock_api_client(standard_status, standard_layers, standard_votemap_config)

def describe_process_map_started():
    @pytest.mark.asyncio
    async def process_map_started_updates_server(
        standard_server_params: ServerParameters, standard_status: ServerStatus, standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()
        whitelists: list[list[str]] = []

        def set_votemap_whitelist(whitelist: list[str]) -> None:
            whitelists.append(whitelist)

        queue = asyncio.Queue()
        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
        api_client.set_votemap_whitelist.side_effect = set_votemap_whitelist
        sut = VotemapManager(standard_server_params, queue, api_client, event_loop)

        # *** ACT ***
        await sut._process_map_started()

        # *** ASSERT ***
        assert len(whitelists) == 2
        assert len(whitelists[0]) == 7
        assert len(whitelists[1]) == 90
        assert api_client.set_votemap_whitelist.call_count == 2
        assert api_client.reset_votemap_state.call_count == 1


def describe_process_map_ended():
    @pytest.mark.asyncio
    async def process_map_ended_saves_history(
        standard_server_params: ServerParameters, standard_status: ServerStatus, standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()
        queue = asyncio.Queue()
        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
        sut = VotemapManager(standard_server_params, queue, api_client, event_loop)
        sut._layer_history.appendleft("utahbeach_warfare")

        # *** ACT ***
        await sut._process_map_ended()

        # *** ASSERT ***
        assert len(sut._layer_history) == 2
        assert sut._layer_history[0] == standard_status.map.id
        assert sut._layer_history[1] == "utahbeach_warfare"


def mock_api_client(
    status: ServerStatus,
    layers: list[Layer],
    votemap_config: VoteMapUserConfig,
) -> AsyncMock:
    client = AsyncMock(spec=CRCONApiClient)
    client.get_status.return_value = status
    client.get_maps.return_value = layers
    client.get_votemap_config.return_value = votemap_config
    client.get_votemap_whitelist.return_value = [layer.id for layer in layers]
    client.set_votemap_whitelist.return_value = None
    client.reset_votemap_state.return_value = None
    return client
