
import pytest
from mongomock_motor import AsyncMongoMockClient

from polebot.app_config import AppConfig
from polebot.models import (
    GuildPlayerGroup,
)
from polebot.services.polebot_database import PolebotDatabase, _GuildPlayerGroupRepository


def describe_test_something():
    @pytest.mark.asyncio
    async def insert_and_find_message_group():
        client = AsyncMongoMockClient(tz_aware=True)
        mock_db = client.get_database("tests")
        repo = _GuildPlayerGroupRepository(db=mock_db)  # type: ignore
        pdb = PolebotDatabase(AppConfig(), mock_db)  # type: ignore

        assert repo.model_desc == "player group"

        obj = GuildPlayerGroup(
            guild_id=1234,
            label="ONE",
            selector="some_stuff",
        )
        inserted = await pdb.insert(obj)

        found = await pdb.find_one(GuildPlayerGroup, 1234, "_id", inserted.id)
        assert found
