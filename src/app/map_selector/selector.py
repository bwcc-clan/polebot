import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Optional

import numpy as np
import pandas as pd

from ..api_models import GameMode, Layer, ServerStatus, Team, VoteMapUserConfig
from ..config import ServerConfig
from .config_loader import get_config_dataframes, get_layer_dataframes

_logger = logging.getLogger(__name__)

class MapSelector:
    def __init__(
        self,
        server_status: ServerStatus,
        layers: Iterable[Layer],
        server_config: ServerConfig,
        votemap_config: VoteMapUserConfig,
        recent_layer_history: Sequence[str],
        logger: logging.Logger = _logger,
    ) -> None:
        """
        Initialises a map selector instance with current state.

        Args:
            server_status (ServerStatus): The current server status.
            layers (Iterable[Layer]): A list of layers that the server supports.
            server_config (ServerConfig): The configuration settings for the server.
            votemap_config (VoteMapUserConfig): The server's votemap configuration.
            recent_layer_history (Iterable[str]): An ordered list of the most recently played map layer IDs,
            most-recently-played last.
            logger (logging.Logger): The logger.
        """

        self._server_status = server_status
        self._layers = layers
        self._recent_layer_history = recent_layer_history
        self._votemap_config = votemap_config
        self._logger = logger

        self._layers_by_id = {layer.id: layer for layer in layers}
        self._current_layer = self._server_status.map

        config_data = get_config_dataframes(server_config)
        self._df_map_groups = config_data.df_map_groups
        self._df_environments = config_data.df_environments
        map_data = get_layer_dataframes(layers=list(layers))
        self._df_warfare = map_data.df_warfare
        self._df_offensive = map_data.df_offensive
        self._df_skirmish = map_data.df_skirmish

        # Always exclude the current layer (map) from selection. Also remove previous n layers from history if
        # configured
        self._standard_exclusions = {self._current_layer.id} & set(
            self._recent_layer_history[: self._votemap_config.number_last_played_to_exclude]
        )

    def get_warfare(self) -> set[str]:
        df = self._prepare_dataframe(self._df_warfare)
        count = self._votemap_config.num_warfare_options

        return self._select_layers(df, count)

    def get_offensive(self) -> set[str]:
        disallow_attackers: Optional[Team] = None
        if self._current_layer.game_mode == GameMode.OFFENSIVE:
            if not self._votemap_config.allow_consecutive_offensives:
                return set()
            if not self._votemap_config.allow_consecutive_offensives_opposite_sides:
                disallow_attackers = Team.AXIS if self._current_layer.attackers == Team.ALLIES else Team.ALLIES


        def process_exclusions(df: pd.DataFrame) -> pd.DataFrame:

            if self._votemap_config.consider_offensive_same_map:
                maps_to_exclude = {
                    self._layers_by_id[layer].map.id
                    for layer in self._recent_layer_history[: self._votemap_config.number_last_played_to_exclude]
                }
                df = df[~df["map.id"].isin(maps_to_exclude)]

            if disallow_attackers:
                df = df[~df["attackers"] == disallow_attackers]

            return df

        df = self._prepare_dataframe(self._df_offensive, prepare=process_exclusions)
        count = self._votemap_config.num_offensive_options
        return self._select_layers(df, count)

    def get_skirmish(self) -> set[str]:
        if self._current_layer.game_mode == GameMode.CONTROL and not self._votemap_config.allow_consecutive_skirmishes:
            return set()

        def process_exclusions(df: pd.DataFrame) -> pd.DataFrame:

            if self._votemap_config.consider_skirmishes_as_same_map:
                maps_to_exclude = {
                    self._layers_by_id[layer].map.id
                    for layer in self._recent_layer_history[: self._votemap_config.number_last_played_to_exclude]
                }
                df = df[~df["map.id"].isin(maps_to_exclude)]

            return df

        df = self._prepare_dataframe(self._df_skirmish, prepare=process_exclusions)
        count = self._votemap_config.num_skirmish_control_options
        return self._select_layers(df, count)

    def _select_layers(self, df: pd.DataFrame, count: int) -> set[str]:
        selected_layers: set[str] = set()

        for i in range(count):
            # (Re)calculate overall weightings. The factors won't have changed (these come from configuration) but the
            # scores are changed in response to the map that has been selected.
            df["overall_weighting"] = (
                df["map_weight"]
                * df["map_count_normalization_factor"]
                * df["environment_weight"]
                * df["environment_count_normalization_factor"]
                * df["map_repeat_score"]
                * df["environment_repeat_score"]
            )

            # Create two arrays of equal length, one with the layer IDs and one with the corresponding weighting
            maps_array = df["id"].to_numpy()
            weights_array = df["overall_weighting"].to_numpy()

            if sum(weights_array) == 0.0:
                break

            # Select a layer for inclusion in the votemap choices
            selected_layer = np.random.choice(maps_array, 1, replace=True, p=(weights_array / sum(weights_array)))[0]
            selected_layers.add(selected_layer)

            # Based on the attributes of the selected layer, modify the weightings of similar layers to reduce their
            # probability of selection
            selected_layer_props = df.loc[df["id"] == selected_layer]
            selected_map_id = selected_layer_props["map.id"].values[0]
            selected_environment_category = selected_layer_props["environment_category"].values[0]

            # Modify weightings based on what has just been chosen
            df.loc[df["map.id"] == selected_map_id, "map_repeat_score"] = df.map_repeat_score * df.map_repeat_decay
            df.loc[df["environment_category"] == selected_environment_category, "environment_repeat_score"] = (
                df.environment_repeat_score * df.environment_repeat_decay
            )
            # Prevent the chosen layer from being chosen again
            df.loc[df["id"] == selected_layer, "map_repeat_score"] = 0.0

        return selected_layers

    def _prepare_dataframe(
        self, df: pd.DataFrame, prepare: Callable[[pd.DataFrame], pd.DataFrame] | None = None
    ) -> pd.DataFrame:

        df[~df["id"].isin(self._standard_exclusions)]
        if prepare:
            df = prepare(df)

        # Calculate the number of instances of each map.id
        map_instance_counts = df.groupby(["map.id"], observed=True).size()
        map_instance_counts.name = "map_instance_count"

        environment_instance_counts = df.groupby(["environment"], observed=True).size()
        environment_instance_counts.name = "environment_instance_count"

        df = (
            df.join(
                map_instance_counts,
                on="map.id",
            )
            .join(
                environment_instance_counts,
                on="environment",
            )
            .join(
                self._df_map_groups,
                on="map.id",
            )
            .join(self._df_environments, on="environment")
        )

        # Validate that all maps are configured - if there are any maps on the server that we haven't had configured
        # then all we can do is log and drop them
        nan_rows = df.loc[df["map_group"].isnull()]
        if len(nan_rows):
            vals = ",".join(nan_rows["map.id"].unique().tolist())
            self._logger.warning("No map groups configured for: %s", vals)
        # Validate that all environments are configured
        nan_rows = df.loc[df["environment_category"].isnull()]
        if len(nan_rows):
            vals = ",".join(nan_rows["environment"].tolist())
            self._logger.warning("No environment groups configured for: %s", vals)
        df = df.dropna(subset=["map_group", "environment_category"])

        # The normalization factors address the fact that some map_ids have more instances (layers) than others, and the
        # same for environments. Without normalization, this would make it more likely to select a map with more layers,
        # or an environment with more instances, which would skew the selection.
        df["map_count_normalization_factor"] = 1 / df["map_instance_count"]
        df["environment_count_normalization_factor"] = 1 / df["environment_instance_count"]

        # Initialize the repeat scores to 1.0, which has no effect on the weightings
        df["map_repeat_score"] = 1.0
        df["environment_repeat_score"] = 1.0

        return df
