"""This module contains functions that load the server configuration and layers into dataframes."""

import pandas as pd
from attrs import define

from crcon.api_models import Layer
from polebot.models import WeightingParameters

from .. import cattrs_helpers


@define(kw_only=True)
class WeightingDataframes:
    """Dataframes that represent the server weighting configuration parameters."""
    df_map_groups: pd.DataFrame
    df_environments: pd.DataFrame


def get_weighting_dataframes(weighting_params: WeightingParameters) -> WeightingDataframes:
    """Gets an object that contains dataframes that represent the server configuration.

    Args:
        weighting_params (WeightingParameters): The structured weighting data to convert to dataframes.

    Returns:
        ConfigData: An object that contains the config dataframes.
    """
    json_converter = cattrs_helpers.make_params_converter()
    config = json_converter.unstructure(weighting_params)

    df_map_groups = (
        (
            pd.DataFrame.from_dict(config["groups"], orient="index")
            .reset_index(names="group")
            .explode("maps")
        )
        .rename(
            columns={
                "maps": "map",
                "weight": "map_weight",
                "group": "map_group",
                "repeat_decay": "map_repeat_decay",
            },
        )
        .set_index("map")
    )

    df_environments = (
        (
            pd.DataFrame.from_dict(config["environments"], orient="index")
            .reset_index(names="environment")
            .explode("environments")
        )
        .rename(
            columns={
                "environment": "environment_category",
                "environments": "environment",
                "weight": "environment_weight",
                "repeat_decay": "environment_repeat_decay",
            },
        )
        .set_index("environment")
    )

    return WeightingDataframes(df_map_groups=df_map_groups, df_environments=df_environments)


@define(kw_only=True)
class LayerData:
    """Dataframes that represent the layers for different game modes in the server configuration."""
    df_warfare: pd.DataFrame
    df_offensive: pd.DataFrame
    df_skirmish: pd.DataFrame


def get_layer_dataframes(layers: list[Layer]) -> LayerData:
    """Gets dataframes that represent the layers for different game modes in the server configuration.

    Args:
        layers (list[Layer]): A list of all layers that the server supports.

    Returns:
        LayerData: An object containing dataframes that represent the layers for different game modes.
    """
    json_converter = cattrs_helpers.make_json_converter()
    l2 = json_converter.unstructure(layers)

    df_maps = pd.json_normalize(
        l2,
        None,
        meta=["id", "environment", "game_mode", ["map", "id", "name", "pretty_name"]],
    )

    # Convert certain columns to categories
    cols = ["game_mode", "environment", "map.id"]
    df_maps[cols] = df_maps[cols].astype("category")

    df_warfare = df_maps.loc[df_maps["game_mode"] == "warfare"]
    df_offensive = df_maps.loc[df_maps["game_mode"] == "offensive"]
    df_skirmish = df_maps.loc[df_maps["game_mode"] == "control"]

    return LayerData(df_warfare=df_warfare, df_offensive=df_offensive, df_skirmish=df_skirmish)
