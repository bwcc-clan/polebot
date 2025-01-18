"""Polebot database layer."""

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from .app_config import AppConfig
from .converters import make_db_converter
from .exceptions import DatastoreError
from .models import GuildServer


class PolebotDatabase:
    """Data store for CRCON server details."""

    def __init__(self, app_config: AppConfig, db: AsyncIOMotorDatabase) -> None:
        """Initialises the configuration repository."""
        self._app_config = app_config
        self._db = db
        self._converter = make_db_converter()

    async def list_guild_servers(self, guild_id: int) -> list[GuildServer]:
        try:
            cursor = self._db.guild_servers.find({"guild_id": {"$eq": guild_id}}).sort("server_name")
            result = [self._converter.structure(doc, GuildServer) for doc in await cursor.to_list(length=100)]
        except Exception as ex:
            raise DatastoreError("Error reading guild server") from ex
        else:
            return result

    async def get_guild_server(self, server_id: ObjectId) -> GuildServer | None:
        try:
            doc = await self._db.guild_servers.find_one({"_id": {"$eq": server_id}})
            result = self._converter.structure(doc, GuildServer) if doc else None
        except Exception as ex:
            raise DatastoreError("Error reading guild server") from ex
        else:
            return result

    async def insert_guild_server(self, guild_details: GuildServer) -> None:
        try:
            doc = self._converter.unstructure(guild_details)
            await self._db.guild_servers.insert_one(doc)
        except Exception as ex:
            raise DatastoreError("Error inserting guild server") from ex

    async def delete_guild_server(self, server_id: ObjectId) -> None:
        try:
            await self._db.guild_servers.delete_one({"_id": {"$eq": server_id}})
        except Exception as ex:
            raise DatastoreError("Error deleting guild server") from ex
