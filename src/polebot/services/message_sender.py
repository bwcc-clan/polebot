from asyncio import Task, TaskGroup
from collections.abc import Iterable

from crcon.api_client import ApiClient
from crcon.exceptions import ApiClientError

from .player_matcher import PlayerMatcher, PlayerProperties


class MessageSender:
    def __init__(self, client: ApiClient) -> None:
        self._client = client

    async def send_group_message(self, player_matcher: PlayerMatcher, message: str) -> Iterable[PlayerProperties]:
        player_ids = await self._client.get_playerids()
        players = [PlayerProperties(name=name, id=player_id) for name, player_id in player_ids]
        matched = [p for p in players if player_matcher.is_match(p)]
        message_task_list: list[tuple[PlayerProperties, Task]] = []

        async def send_message(player_id: str, message: str) -> bool:
            try:
                await self._client.message_player(player_id, message)
            except ApiClientError:
                return False
            return True

        async with TaskGroup() as tg:
            for player in matched:
                task = tg.create_task(send_message(player.id, message))
                message_task_list.append((player, task))

        return [p for p, task in message_task_list if not task.exception() and task.result()]
