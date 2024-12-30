import json

import pytest
from utils import support_files_dir

import app.converters as converters
from app.api_models import (
    ApiResult,
    Layer,
    ServerStatus,
    VoteMapUserConfig,
)
from app.config import EnvironmentGroupConfig, MapGroupConfig, ServerConfig, ServerCRCONDetails, WeightingConfig
from app.map_selector.selector import MapSelector

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
    def standard_config() -> ServerConfig:
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
        current_map = "carentan_warfare_night"
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
            standard_config: ServerConfig, standard_status: ServerStatus, standard_layers_by_id: dict[str, Layer]
        ):
            # *** ARRANGE ***
            vmuc = VoteMapUserConfig(num_warfare_options=6)
            sut = MapSelector(standard_status, list(standard_layers_by_id.values()), standard_config, vmuc, [])

            # *** ACT ***
            result = sut.get_warfare()

            # *** ASSERT ***
            assert len(result) == 6

        def selects_configured_number_of_offensive(
            standard_config: ServerConfig, standard_status: ServerStatus, standard_layers_by_id: dict[str, Layer]
        ):
            # *** ARRANGE ***
            vmuc = VoteMapUserConfig(num_offensive_options=6)
            sut = MapSelector(standard_status, list(standard_layers_by_id.values()), standard_config, vmuc, [])

            # *** ACT ***
            result = sut.get_offensive()

            # *** ASSERT ***
            assert len(result) == 6

        def selects_configured_number_of_skirmish(
            standard_config: ServerConfig, standard_status: ServerStatus, standard_layers_by_id: dict[str, Layer]
        ):
            # *** ARRANGE ***
            vmuc = VoteMapUserConfig(num_skirmish_control_options=6)
            sut = MapSelector(standard_status, list(standard_layers_by_id.values()), standard_config, vmuc, [])

            # *** ACT ***
            result = sut.get_skirmish()

            # *** ASSERT ***
            assert len(result) == 6
