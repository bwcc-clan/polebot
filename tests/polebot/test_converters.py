import datetime as dt
import json
import os
from types import NoneType
from typing import Any

import pytest
from bson import ObjectId
from cattr import Converter
from cattrs.preconf.bson import BsonConverter
from cattrs.preconf.json import JsonConverter
from utils import support_files_dir
from yarl import URL

import polebot.converters as converters
from polebot.api_models import (
    ApiResult,
    ApiResultWithArgs,
    DefaultMethods,
    Environment,
    GameMode,
    Layer,
    LogMessageType,
    LogStreamResponse,
    Orientation,
    SetVotemapWhitelistParams,
    Team,
    VoteMapUserConfig,
)
from polebot.models import GuildServer, ServerCRCONDetails, ServerParameters

SUPPORT_FILES_DIR = support_files_dir(__file__)


def describe_structure():
    def describe_with_simple_result():
        @pytest.fixture
        def converter() -> JsonConverter:
            return converters.make_params_converter()

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
            return converters.make_rcon_converter()

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
            return converters.make_rcon_converter()

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
            return converters.make_rcon_converter()

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

    def describe_with_logstream_response():
        @pytest.fixture
        def converter() -> JsonConverter:
            return converters.make_rcon_converter()

        @pytest.fixture
        def contents() -> Any:
            filepath = SUPPORT_FILES_DIR.joinpath("logstream_response.json")
            with filepath.open() as f:
                contents = json.load(f)
            return contents

        def can_read_config(converter: JsonConverter, contents: Any):
            response = converter.structure(contents, LogStreamResponse)
            assert response.error is None
            assert response.last_seen_id == "1731972329-0"
            assert len(response.logs) == 3
            assert response.logs[0].id == "1731955604-1"
            assert response.logs[0].log.action == LogMessageType.message
            assert response.logs[0].log.event_time.year == 2024
            assert response.logs[1].id == "1731955686-0"
            assert response.logs[1].log.player_name_1 == "Bjørn"
            assert response.logs[2].id == "1731972329-0"
            assert response.logs[2].log.action == LogMessageType.match_start

def describe_params_converter():
    @pytest.fixture
    def converter() -> JsonConverter:
        return converters.make_params_converter()

    def describe_with_server_params():
        @pytest.fixture
        def contents() -> Any:
            filepath = SUPPORT_FILES_DIR.joinpath("server_params.json")
            with filepath.open() as f:
                contents = json.load(f)
            return contents

        def can_read_config(converter: JsonConverter, contents: Any):
            os.environ["SOME_ENV_VAR"] = "magic_value"
            config = converter.structure(contents, ServerParameters)
            assert config is not None
            assert config.server_name == "My Test Server"
            assert config.crcon_details is not None
            assert config.crcon_details.api_url == URL("https://hll.example.com")
            assert config.crcon_details.api_key == "magic_value"
            assert config.crcon_details.websocket_url.scheme == "wss"
            assert config.crcon_details.websocket_url.host == config.crcon_details.api_url.host
            assert config.weighting_params is not None

            assert len(config.weighting_params.groups) == 3
            assert "Boost" in config.weighting_params.groups
            boost1 = config.weighting_params.groups["Boost"]
            assert boost1.weight == 80
            assert boost1.repeat_decay == 0.6
            assert len(config.weighting_params.environments) == 3

def describe_db_converter():
    @pytest.fixture
    def converter() -> BsonConverter:
        return converters.make_db_converter()

    def describe_with_guild_server():

        def can_unstructure(converter: Converter):
            # ***** ARRANGE *****
            guild_server = GuildServer(
                guild_id=12345,
                server_name="server_name",
                crcon_details=ServerCRCONDetails("https://server.example.com", "some key"),
                created_date_utc=dt.datetime.now(dt.UTC),
            )

            # ***** ACT *****
            result = converter.unstructure(guild_server)

            # ***** ASSERT *****
            assert result["guild_id"] == 12345
            assert isinstance(result["_id"], ObjectId)
            assert result["crcon_details"]["api_url"] == "https://server.example.com"

        def can_structure(converter: Converter):
            # ***** ARRANGE *****
            db_rec = {
                "_id": ObjectId(b"foo-bar-quux"),
                "guild_id": 12345,
                "server_name": "server_name",
                "crcon_details": {"api_url": "https://server.example.com", "api_key": "some key"},
            }

            # ***** ACT *****
            result = converter.structure(db_rec, GuildServer)

            # ***** ASSERT *****
            assert result.guild_id == 12345
            assert result.id == ObjectId(b"foo-bar-quux")
            assert result.server_name == "server_name"
            assert result.crcon_details.api_url == URL("https://server.example.com")
