import json
from collections import deque

import pytest
from utils import support_files_dir

import app.converters as converters
from app.api_models import (
    ApiResult,
    GameMode,
    Layer,
    ServerStatus,
    VoteMapUserConfig,
)
from app.config import EnvironmentGroupConfig, MapGroupConfig, ServerConfig, ServerCRCONDetails, WeightingConfig
from app.map_selector.selector import _SKIRMISH_MODES, MapSelector

SUPPORT_FILES_DIR = support_files_dir(__file__)


def describe_get_warfare():
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
    def standard_server_config() -> ServerConfig:
        crcon_details = ServerCRCONDetails(api_url="https://hll.example.com", api_key="dummy")
        weighting_config = WeightingConfig(
            groups={
                "Top": MapGroupConfig(
                    weight=100,
                    repeat_decay=0.8,
                    maps=["carentan", "omahabeach", "stmariedumont", "stmereeglise", "utahbeach"],
                ),
                "Mid": MapGroupConfig(
                    weight=80,
                    repeat_decay=0.5,
                    maps=["elsenbornridge", "foy", "hill400"],
                ),
            },
            environments={
                "Day": EnvironmentGroupConfig(weight=100, repeat_decay=0.8, environments=["day", "dawn"]),
                "Night": EnvironmentGroupConfig(weight=50, repeat_decay=0.1, environments=["night"]),
            },
        )
        return ServerConfig(server_name="Test", crcon_details=crcon_details, weighting_config=weighting_config)

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
    def standard_votemap_config() -> VoteMapUserConfig:
        return VoteMapUserConfig(num_warfare_options=6, num_offensive_options=2, num_skirmish_control_options=2)

    @pytest.fixture
    def status_current_layer_offensive_us(standard_layers_by_id: dict[str, Layer]) -> ServerStatus:
        current_map = "carentan_offensive_us"
        return ServerStatus(
            name="Test",
            map=standard_layers_by_id[current_map],
            current_players=2,
            max_players=2,
            short_name="TEST",
            server_number=1,
        )

    def describe_happy_path():
        def selects_configured_number_of_warfare(
            standard_server_config: ServerConfig, standard_status: ServerStatus, standard_layers_by_id: dict[str, Layer]
        ):
            # *** ARRANGE ***
            vmuc = VoteMapUserConfig(num_warfare_options=6)
            sut = MapSelector(standard_status, list(standard_layers_by_id.values()), standard_server_config, vmuc, [])

            # *** ACT ***
            result = sut._get_warfare()

            # *** ASSERT ***
            assert len(list(result)) == 6

        def selects_configured_number_of_offensive(
            standard_server_config: ServerConfig, standard_status: ServerStatus, standard_layers_by_id: dict[str, Layer]
        ):
            # *** ARRANGE ***
            vmuc = VoteMapUserConfig(num_offensive_options=6)
            sut = MapSelector(standard_status, list(standard_layers_by_id.values()), standard_server_config, vmuc, [])

            # *** ACT ***
            result = sut._get_offensive()

            # *** ASSERT ***
            assert len(list(result)) == 6

        def selects_configured_number_of_skirmish(
            standard_server_config: ServerConfig, standard_status: ServerStatus, standard_layers_by_id: dict[str, Layer]
        ):
            # *** ARRANGE ***
            vmuc = VoteMapUserConfig(num_skirmish_control_options=6)
            sut = MapSelector(standard_status, list(standard_layers_by_id.values()), standard_server_config, vmuc, [])

            # *** ACT ***
            result = sut._get_skirmish()

            # *** ASSERT ***
            assert len(list(result)) == 6

    def describe_with_map_history_as_deque():
        def selects_configured_number_of_warfare(
            standard_server_config: ServerConfig, standard_status: ServerStatus, standard_layers_by_id: dict[str, Layer]
        ):
            # *** ARRANGE ***
            vmuc = VoteMapUserConfig(num_warfare_options=6, number_last_played_to_exclude=1)
            recent_layer_history = deque(
                ["carentan_warfare_night", "omahabeach_warfare_day", "stmariedumont_warfare_day"], maxlen=3
            )
            sut = MapSelector(
                standard_status,
                list(standard_layers_by_id.values()),
                standard_server_config,
                vmuc,
                recent_layer_history,
            )

            # *** ACT ***
            result = sut._get_warfare()

            # *** ASSERT ***
            assert len(list(result)) == 6

    def describe_analyze_results():
        @pytest.fixture
        def results_no_history(
            standard_server_config: ServerConfig,
            standard_status: ServerStatus,
            standard_layers_by_id: dict[str, Layer],
            standard_votemap_config: VoteMapUserConfig,
        ):
            return _generate_some_results(
                standard_server_config, standard_status, standard_layers_by_id, standard_votemap_config
            )

        @pytest.fixture
        def results_current_map_offensive_us(
            standard_server_config: ServerConfig,
            status_current_layer_offensive_us: ServerStatus,
            standard_layers_by_id: dict[str, Layer],
            standard_votemap_config: VoteMapUserConfig,
        ):
            return _generate_some_results(
                standard_server_config,
                status_current_layer_offensive_us,
                standard_layers_by_id,
                standard_votemap_config,
            )

        def results_are_ordered_correctly(results_no_history: list[list[str]], standard_layers_by_id: dict[str, Layer]):
            for result_set in results_no_history:
                layers = [standard_layers_by_id[layer] for layer in result_set]

                def get_sequence(layer: Layer) -> int:
                    if layer.game_mode == GameMode.WARFARE:
                        return 1
                    if layer.game_mode == GameMode.OFFENSIVE:
                        return 2
                    if layer.game_mode in _SKIRMISH_MODES:
                        return 3
                    return -1

                current = 0
                for i in range(len(layers)):
                    assert get_sequence(layers[i]) >= current, f"Layers are not ordered correctly: {layers}"

        def current_layer_not_present(results_no_history: list[list[str]], standard_status: ServerStatus):
            current_layer = standard_status.map.id
            for result_set in results_no_history:
                assert current_layer not in result_set, f"Current layer {current_layer} is present: {result_set}"

        def no_consecutive_offensives(
            standard_layers_by_id: dict[str, Layer],
            standard_server_config: ServerConfig,
            status_current_layer_offensive_us: ServerStatus,
        ):
            votemap_config = VoteMapUserConfig(
                num_warfare_options=6,
                num_offensive_options=2,
                num_skirmish_control_options=2,
                allow_consecutive_offensives=False,
            )
            results = _generate_some_results(
                standard_server_config, status_current_layer_offensive_us, standard_layers_by_id, votemap_config
            )
            for result_set in results:
                layers = [standard_layers_by_id[layer] for layer in result_set]
                assert GameMode.OFFENSIVE not in [layer.game_mode for layer in layers]


def _generate_some_results(
    server_config: ServerConfig,
    server_status: ServerStatus,
    layers_by_id: dict[str, Layer],
    votemap_config: VoteMapUserConfig,
) -> list[list[str]]:
    sut = MapSelector(server_status, list(layers_by_id.values()), server_config, votemap_config, [])
    result_sets: list[list[str]] = []
    for i in range(50):
        result_sets.append(list(sut.get_selection()))
    return result_sets
