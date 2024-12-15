from collections.abc import Iterable, Sequence

from .models import GameMode, Layer, ServerStatus, VoteMapUserConfig


class MapSelector:
    def __init__(
        self,
        server_status: ServerStatus,
        layers: Iterable[Layer],
        votemap_config: VoteMapUserConfig,
        map_history: Sequence[str],
    ) -> None:
        """
        Initialises a map selector instance with current state.

        Args:
            server_status (ServerStatus): The current server status.
            layers (Iterable[Layer]): A list of layers that the server supports.
            votemap_config (VoteMapUserConfig): The server's votemap configuration.
            map_history (Iterable[str]): An ordered list of the most recently played map layer IDs, most-recently-played last.
        """
        self._server_status = server_status
        self._layers = {layer.id: layer for layer in layers}
        self._votemap_config = votemap_config
        self._map_history = map_history

    def generate_selection(self) -> Iterable[str]:
        recent_history_count = self._votemap_config.number_last_played_to_exclude
        recent_map_history = [x for x in self._map_history[-recent_history_count:]]

        gen = WeightingGenerator(self._layers, recent_map_history)
        return None


class WeightingGenerator:
    def __init__(
        self,
        layers: dict[str, Layer],
        recent_map_history: Sequence[str],
    ) -> None:
        self._layers = layers
        self._recent_map_history = recent_map_history

        self._recent_history = [self._layers[x] for x in recent_map_history]
        self._warfare_layers = [layer for layer in self._layers.values() if layer.game_mode == GameMode.WARFARE]
        self._offensive_layers = [layer for layer in self._layers.values() if layer.game_mode == GameMode.OFFENSIVE]
        self._skirmish_layers = [layer for layer in self._layers.values() if layer.game_mode == GameMode.CONTROL]

    def calculate_warfare_weightings(self) -> tuple[list[Layer], list[int]]:
        warfare_weights = [100 for _ in self._warfare_layers]
        return (self._warfare_layers, warfare_weights)

    def calculate_offensive_weightings(self) -> tuple[list[Layer], list[int]]:
        offensive_weights = [100 for _ in self._offensive_layers]
        return (self._offensive_layers, offensive_weights)


    def calculate_skirmish_weightings(self) -> tuple[list[Layer], list[int]]:
        skirmish_weights = [100 for _ in self._skirmish_layers]
        return (self._skirmish_layers, skirmish_weights)

