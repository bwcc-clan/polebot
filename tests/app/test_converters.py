import json
from types import NoneType
from typing import Any

import pytest
from cattrs.preconf.json import JsonConverter
from utils import support_files_dir

import app.converters as converters
from app.models import (
    ApiResult,
    ApiResultWithArgs,
    DefaultMethods,
    Environment,
    GameMode,
    Layer,
    Orientation,
    SetVotemapWhitelistParams,
    Team,
    VoteMapUserConfig,
)

SUPPORT_FILES_DIR = support_files_dir(__file__)


def describe_structure():
    def describe_with_simple_result():
        @pytest.fixture
        def converter() -> JsonConverter:
            return converters.converter

        def success_result(converter: JsonConverter):
            json_content = """
            {
                "result": 5,
                "command": "simple_test",
                "arguments": {},
                "failed": false,
                "error": null,
                "forward_results": null,
                "version": "v10.5.1"
            }
            """
            contents = json.loads(json_content)
            api_result = converter.structure(contents, ApiResult[int])
            assert api_result.failed is False
            assert api_result.result == 5
            assert api_result.error is None
            assert api_result.version == "v10.5.1"
            assert api_result.command == "simple_test"

        def failed_result(converter: JsonConverter):
            json_content = """
            {
                "result": null,
                "command": "simple_test",
                "arguments": {},
                "failed": true,
                "error": "Error message",
                "forward_results": null,
                "version": "v10.5.1"
            }
            """
            contents = json.loads(json_content)
            api_result = converter.structure(contents, ApiResult[int])
            assert api_result.failed is True
            assert api_result.result is None
            assert api_result.error == "Error message"

    def describe_with_get_maps():
        @pytest.fixture
        def converter() -> JsonConverter:
            return converters.converter

        @pytest.fixture
        def contents() -> Any:
            filepath = SUPPORT_FILES_DIR.joinpath("get_maps.json")
            with filepath.open() as f:
                contents = json.load(f)
            return contents

        def can_read_api_result(converter: JsonConverter, contents: Any):
            layers = converter.structure(contents, ApiResult[list[Layer]])
            assert layers.failed is False
            assert layers.result
            assert len(layers.result) == 90

        def can_read_skirmish_map(converter: JsonConverter, contents: Any):
            api_result = converter.structure(contents, ApiResult[list[Layer]])
            assert api_result.result
            layer = next(lyr for _, lyr in enumerate(api_result.result) if lyr.id == "CAR_S_1944_Day_P_Skirmish")
            assert layer.game_mode == GameMode.CONTROL
            assert layer.attackers is None
            assert layer.map.id == "carentan"
            assert layer.map.pretty_name == "Carentan"
            assert layer.map.orientation == Orientation.HORIZONTAL
            assert layer.map.allies.name == "us"
            assert layer.map.axis.name == "ger"

        def can_read_offensive_map(converter: JsonConverter, contents: Any):
            api_result = converter.structure(contents, ApiResult[list[Layer]])
            assert api_result.result
            layer = next(lyr for _, lyr in enumerate(api_result.result) if lyr.id == "PHL_L_1944_OffensiveGER")
            assert layer.game_mode == GameMode.OFFENSIVE
            assert layer.attackers == Team.AXIS
            assert layer.map.id == "purpleheartlane"
            assert layer.map.pretty_name == "Purple Heart Lane"
            assert layer.map.orientation == Orientation.VERTICAL
            assert layer.map.allies.name == "us"
            assert layer.map.axis.name == "ger"
            assert layer.environment == Environment.DAY

        def can_read_warfare_map(converter: JsonConverter, contents: Any):
            api_result = converter.structure(contents, ApiResult[list[Layer]])
            assert api_result.result
            layer = next(lyr for _, lyr in enumerate(api_result.result) if lyr.id == "driel_warfare")
            assert layer.game_mode == GameMode.WARFARE
            assert layer.attackers is None
            assert layer.map.id == "driel"
            assert layer.map.pretty_name == "Driel"
            assert layer.map.orientation == Orientation.VERTICAL
            assert layer.map.allies.name == "gb"
            assert layer.map.axis.name == "ger"
            assert layer.environment == Environment.DAY
            assert layer.pretty_name == "Driel Warfare"

    def describe_with_get_votemap_config():
        @pytest.fixture
        def converter() -> JsonConverter:
            return converters.converter

        @pytest.fixture
        def contents() -> Any:
            filepath = SUPPORT_FILES_DIR.joinpath("get_votemap_config.json")
            with filepath.open() as f:
                contents = json.load(f)
            return contents

        def can_read_config(converter: JsonConverter, contents: Any):
            api_result = converter.structure(contents, ApiResult[VoteMapUserConfig])
            assert api_result.failed is False
            assert api_result.result
            assert api_result.result.allow_consecutive_offensives is False
            assert api_result.result.allow_consecutive_offensives_opposite_sides is False
            assert api_result.result.no_vote_text == "No votes recorded yet"
            assert api_result.result.default_method == DefaultMethods.random_all_maps

    def describe_with_set_votemap_whitelist():
        @pytest.fixture
        def converter() -> JsonConverter:
            return converters.converter

        @pytest.fixture
        def contents() -> Any:
            filepath = SUPPORT_FILES_DIR.joinpath("set_votemap_whitelist.json")
            with filepath.open() as f:
                contents = json.load(f)
            return contents

        def can_read_result(converter: JsonConverter, contents: Any):
            api_result = converter.structure(contents, ApiResultWithArgs[NoneType, SetVotemapWhitelistParams])
            assert api_result.failed is False
            assert api_result.result is None
            assert api_result.arguments.map_names == [
                "stalingrad_warfare_night",
                "carentan_warfare",
                "mortain_offensiveUS_overcast",
                "hurtgenforest_offensive_ger",
                "PHL_L_1944_Warfare_Night",
                "carentan_warfare_night",
            ]
