import json
from typing import Any

import pytest
from cattrs.preconf.json import JsonConverter
from utils import support_files_dir

from app import converters
from app.api_models import ApiResult, Layer
from app.config import EnvironmentGroupConfig, MapGroupConfig, ServerConfig, ServerCRCONDetails, WeightingConfig
from app.map_selector.config_loader import get_config_dataframes, get_layer_dataframes

SUPPORT_FILES_DIR = support_files_dir(__file__)

def describe_get_config_dataframes():
    def describe_loads_dataframes():
        @pytest.fixture
        def config() -> ServerConfig:
            crcon_details = ServerCRCONDetails(api_url="https://hll.example.com", api_key="test_key")
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

        def df_map_groups_contents_are_mapped(config: ServerConfig):
            data = get_config_dataframes(config)

            assert data.df_map_groups.shape == (8, 3)
            expected_columns = {"map_group", "map_weight", "map_repeat_decay"}
            assert set(data.df_map_groups.columns) == set(expected_columns)
            assert set(data.df_map_groups.itertuples(name=None)) == {
                ("utahbeach", "Top", 100, 0.8),
                ("stmariedumont", "Top", 100, 0.8),
                ("stmereeglise", "Top", 100, 0.8),
                ("omahabeach", "Top", 100, 0.8),
                ("carentan", "Top", 100, 0.8),
                ("elsenbornridge", "Mid", 80, 0.5),
                ("foy", "Mid", 80, 0.5),
                ("hill400", "Mid", 80, 0.5),
            }

        def df_environments_contents_are_mapped(config: ServerConfig):
            data = get_config_dataframes(config)

            assert data.df_environments.shape == (3, 3)
            expected_columns = {"environment_category", "environment_weight", "environment_repeat_decay"}
            assert set(data.df_environments.columns) == set(expected_columns)
            assert set(data.df_environments.itertuples(name=None)) == {
                ("day", "Day", 100, 0.8),
                ("dawn", "Day", 100, 0.8),
                ("night", "Night", 50, 0.1),
            }

def describe_get_map_dataframe():
    def describe_loads_dataframes():
        @pytest.fixture
        def converter() -> JsonConverter:
            return converters.make_config_converter()

        @pytest.fixture
        def contents() -> Any:
            filepath = SUPPORT_FILES_DIR.joinpath("get_maps.json")
            with filepath.open() as f:
                contents = json.load(f)
            return contents

        @pytest.fixture
        def layers(converter: JsonConverter, contents: Any) -> list[Layer]:
            api_result = converter.structure(contents, ApiResult[list[Layer]])
            assert api_result.result is not None
            return api_result.result

        def loads_all_maps(layers: list[Layer]):
            x = get_layer_dataframes(layers)
            assert len(x.df_warfare) == 32
            assert len(x.df_offensive) == 36
            assert len(x.df_skirmish) == 22
            assert (len(layers)) == 32 + 36 + 22
