import pandas as pd
from attrs import define

from .. import converters
from ..api_models import Layer
from ..config import ServerConfig


@define(kw_only=True)
class ConfigData:
    df_map_groups: pd.DataFrame
    df_environments: pd.DataFrame


def get_config_dataframes(server_config: ServerConfig) -> ConfigData:
    """
    Gets an object that contains dataframes that represent the server configuration.

    Args:
        server_config (ServerConfig): The server configuration to read from.

    Returns:
        ConfigData: An object that contains the config dataframes.
    """

    json_converter = converters.make_config_converter()
    config = json_converter.unstructure(server_config)

    df_map_groups = (
        (
            pd.DataFrame.from_dict(config["weighting_config"]["groups"], orient="index")
            .reset_index(names="group")
            .explode("maps")
        )
        .rename(
            columns={
                "maps": "map",
                "weight": "map_weight",
                "group": "map_group",
                "repeat_decay": "map_repeat_decay",
            }
        )
        .set_index("map")
    )

    df_environments = (
        (
            pd.DataFrame.from_dict(config["weighting_config"]["environments"], orient="index")
            .reset_index(names="environment")
            .explode("environments")
        )
        .rename(
            columns={
                "environment": "environment_category",
                "environments": "environment",
                "weight": "environment_weight",
                "repeat_decay": "environment_repeat_decay",
            }
        )
        .set_index("environment")
    )

    return ConfigData(df_map_groups=df_map_groups, df_environments=df_environments)


@define(kw_only=True)
class LayerData:
    df_warfare: pd.DataFrame
    df_offensive: pd.DataFrame
    df_skirmish: pd.DataFrame


def get_layer_dataframes(layers: list[Layer]) -> LayerData:
    json_converter = converters.make_rcon_converter()
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
