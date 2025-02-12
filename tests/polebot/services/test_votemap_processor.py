import asyncio
import datetime as dt
import json
from unittest.mock import AsyncMock

import pytest
from testutils import support_files_dir

from crcon import ApiClient, converters
from crcon.api_models import (
    ApiResult,
    Layer,
    LogMessageType,
    LogStreamObject,
    ServerStatus,
    StructuredLogLineWithMetaData,
    VoteMapUserConfig,
)
from polebot.models import (
    EnvironmentGroup,
    MapGroup,
    WeightingParameters,
)
from polebot.services.votemap_processor import VotemapProcessor

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
def standard_weighting_params() -> WeightingParameters:
    return WeightingParameters(
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
        standard_weighting_params: WeightingParameters,
        standard_status: ServerStatus,
        standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()
        whitelists: list[list[str]] = []

        def set_votemap_whitelist(whitelist: list[str]) -> None:
            whitelists.append(whitelist)

        queue = asyncio.Queue()
        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
        api_client.set_votemap_whitelist.side_effect = set_votemap_whitelist
        sut = VotemapProcessor(queue, api_client, event_loop)
        sut.weighting_params = standard_weighting_params
        sut.enabled = True

        # *** ACT ***
        await sut._process_map_started()

        # *** ASSERT ***
        assert len(whitelists) == 2
        assert len(whitelists[0]) == 7
        assert len(whitelists[1]) == 90
        assert api_client.set_votemap_whitelist.call_count == 2
        assert api_client.reset_votemap_state.call_count == 1


def when_instance_is_created():
    @pytest.mark.asyncio
    async def can_be_created_with_queue(
        standard_api_client: ApiClient,
        standard_status: ServerStatus,
        standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()
        queue = asyncio.Queue()
        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())

        # *** ACT ***
        sut = VotemapProcessor(queue, api_client, event_loop)

        # *** ASSERT ***
        assert sut.enabled is False


def describe_setting_enabled_flag():
    def when_weighting_parameters_set():
        @pytest.mark.asyncio
        async def can_set_enabled_flag(
            standard_weighting_params: WeightingParameters,
            standard_status: ServerStatus,
            standard_layers: list[Layer],
        ):
            # *** ARRANGE ***
            event_loop = asyncio.get_event_loop()
            queue = asyncio.Queue()
            api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
            sut = VotemapProcessor(queue, api_client, event_loop)
            sut.weighting_params = standard_weighting_params

            # *** ACT ***
            sut.enabled = True

            # *** ASSERT ***
            assert sut.enabled is True

        @pytest.mark.asyncio
        async def can_clear_enabled_flag(
            standard_weighting_params: WeightingParameters,
            standard_status: ServerStatus,
            standard_layers: list[Layer],
        ):
            # *** ARRANGE ***
            event_loop = asyncio.get_event_loop()
            queue = asyncio.Queue()
            api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
            sut = VotemapProcessor(queue, api_client, event_loop)
            sut.weighting_params = standard_weighting_params
            sut.enabled = True

            # *** ACT ***
            sut.enabled = False

            # *** ASSERT ***
            assert sut.enabled is False

    def when_weighting_parameters_not_set():
        @pytest.mark.asyncio
        async def setting_enabled_flag_raises(
            standard_weighting_params: WeightingParameters,
            standard_status: ServerStatus,
            standard_layers: list[Layer],
        ):
            # *** ARRANGE ***
            event_loop = asyncio.get_event_loop()
            queue = asyncio.Queue()
            api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
            sut = VotemapProcessor(queue, api_client, event_loop)

            # *** ACT ***
            with pytest.raises(ValueError) as exc_info:
                sut.enabled = True

            # *** ASSERT ***
            assert str(exc_info.value) == "Cannot enable votemap processor without configuring weighting parameters"


def when_receiving_map_started_message():
    @pytest.mark.asyncio
    async def message_ignored_if_not_enabled(
        standard_weighting_params: WeightingParameters,
        standard_status: ServerStatus,
        standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()
        whitelists: list[list[str]] = []

        def set_votemap_whitelist(whitelist: list[str]) -> None:
            whitelists.append(whitelist)

        queue = asyncio.Queue[LogStreamObject]()
        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
        api_client.set_votemap_whitelist.side_effect = set_votemap_whitelist
        sut = VotemapProcessor(queue, api_client, event_loop)
        map_started = create_log_stream_object(LogMessageType.match_start)

        # *** ACT ***
        async with asyncio.TaskGroup() as tg:
            task = tg.create_task(sut.run())
            await queue.put(map_started)
            await asyncio.sleep(2.0)
            queue.shutdown()
            await task

        # *** ASSERT ***
        assert len(whitelists) == 0
        assert api_client.set_votemap_whitelist.call_count == 0
        assert api_client.reset_votemap_state.call_count == 0

    @pytest.mark.asyncio
    async def message_processed_if_enabled(
        standard_weighting_params: WeightingParameters,
        standard_status: ServerStatus,
        standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()
        whitelists: list[list[str]] = []

        def set_votemap_whitelist(whitelist: list[str]) -> None:
            whitelists.append(whitelist)

        queue = asyncio.Queue[LogStreamObject]()

        def cancel_task():
            queue.shutdown()

        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
        api_client.set_votemap_whitelist.side_effect = set_votemap_whitelist
        api_client.reset_votemap_state.side_effect = cancel_task

        sut = VotemapProcessor(queue, api_client, event_loop)
        sut.weighting_params = standard_weighting_params
        sut.enabled = True

        map_started = create_log_stream_object(LogMessageType.match_start)

        # *** ACT ***
        async with asyncio.TaskGroup() as tg:
            task = tg.create_task(sut.run())
            await queue.put(map_started)
            await asyncio.sleep(0.1)
            await task

        # *** ASSERT ***
        assert len(whitelists) == 2
        assert len(whitelists[0]) == 7
        assert len(whitelists[1]) == 90
        assert api_client.set_votemap_whitelist.call_count == 2
        assert api_client.reset_votemap_state.call_count == 1


def when_receiving_map_ended_message():
    @pytest.mark.asyncio
    async def message_ignored_if_not_enabled(
        standard_weighting_params: WeightingParameters,
        standard_status: ServerStatus,
        standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()
        whitelists: list[list[str]] = []

        def set_votemap_whitelist(whitelist: list[str]) -> None:
            whitelists.append(whitelist)

        queue = asyncio.Queue[LogStreamObject]()
        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
        api_client.set_votemap_whitelist.side_effect = set_votemap_whitelist
        sut = VotemapProcessor(queue, api_client, event_loop)
        map_ended = create_log_stream_object(LogMessageType.match_end)

        # *** ACT ***
        async with asyncio.TaskGroup() as tg:
            task = tg.create_task(sut.run())
            await queue.put(map_ended)
            await asyncio.sleep(2.0)
            queue.shutdown()
            await task

        # *** ASSERT ***
        assert len(whitelists) == 0
        assert api_client.set_votemap_whitelist.call_count == 0
        assert api_client.reset_votemap_state.call_count == 0

    @pytest.mark.asyncio
    async def message_processed_if_enabled(
        standard_weighting_params: WeightingParameters,
        standard_status: ServerStatus,
        standard_layers: list[Layer],
    ):
        # *** ARRANGE ***
        event_loop = asyncio.get_event_loop()

        queue = asyncio.Queue[LogStreamObject]()

        def cancel_task():
            queue.shutdown()

        api_client = mock_api_client(standard_status, standard_layers, VoteMapUserConfig())
        sut = VotemapProcessor(queue, api_client, event_loop)
        sut._layer_history.appendleft("utahbeach_warfare")

        map_ended = create_log_stream_object(LogMessageType.match_end)

        sut.weighting_params = standard_weighting_params
        sut.enabled = True

        # *** ACT ***
        async with asyncio.TaskGroup() as tg:
            task = tg.create_task(sut.run())
            await queue.put(map_ended)
            await asyncio.sleep(0.1)
            queue.shutdown()
            await task

        # *** ASSERT ***
        assert len(sut._layer_history) == 2
        assert sut._layer_history[0] == standard_status.map.id
        assert sut._layer_history[1] == "utahbeach_warfare"


def mock_api_client(
    status: ServerStatus,
    layers: list[Layer],
    votemap_config: VoteMapUserConfig,
) -> AsyncMock:
    client = AsyncMock(spec=ApiClient)
    client.get_status.return_value = status
    client.get_maps.return_value = layers
    client.get_votemap_config.return_value = votemap_config
    client.get_votemap_whitelist.return_value = [layer.id for layer in layers]
    client.set_votemap_whitelist.return_value = None
    client.reset_votemap_state.return_value = None
    return client


def create_log_stream_object(action: LogMessageType) -> LogStreamObject:
    return LogStreamObject(
        id="1",
        log=StructuredLogLineWithMetaData(
            message="Map started",
            version=1,
            timestamp_ms=0,
            event_time=dt.datetime.now(dt.UTC),
            raw="",
            relative_time_ms=0,
            line_without_time="",
            action=action,
            player_name_1=None,
            player_id_1=None,
            player_name_2=None,
            player_id_2=None,
            weapon=None,
            sub_content=None,
        ),
    )
