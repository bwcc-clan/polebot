"""Polebot database layer."""

from collections.abc import Iterable, Sequence
from typing import Any, cast, get_args

import pymongo
import pymongo.errors
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..app_config import AppConfig
from ..exceptions import DatastoreError, DuplicateKeyError
from ..models import GuildDbModel, GuildPlayerGroup, GuildServer
from .converters import make_db_converter


class PolebotDatabase:
    """Data store for CRCON server details."""

    def __init__(self, app_config: AppConfig, db: AsyncIOMotorDatabase) -> None:
        """Initialises the configuration repository."""
        self._app_config = app_config
        self._db = db
        self._converter = make_db_converter()

    async def initialize(self) -> None:
        for repo in _GuildRepository.repository_map.values():
            for index in repo.get_indexes():
                await self._db[repo.collection_name].create_index(index.keys, **index.props)

    async def insert[T: GuildDbModel](self, obj: T) -> ObjectId: # type: ignore[reportInvalidTypeVarUse]
        cls = type(obj)
        repo_type = _GuildRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        return await repo.insert(obj)

    async def list[T: GuildDbModel](self, cls: type[T], guild_id: int, *, sort: str | None = None) -> list[T]:
        repo_type = _GuildRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        try:
            docs = await repo.list_all(guild_id, sort=sort)
        except Exception as ex:
            raise DatastoreError(f"Error reading {repo.model_desc} list") from ex
        else:
            return docs

    async def find_one[T: GuildDbModel](self, cls: type[T], guild_id: int, attr_name: str, attr_value: Any) -> T | None:  # noqa: ANN401
        repo_type = _GuildRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        return await repo.find_one(guild_id, attr_name=attr_name, attr_value=attr_value)

    async def delete[T: GuildDbModel](self, cls: type[T], doc_id: ObjectId) -> None:
        repo_type = _GuildRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        try:
            await repo.delete(doc_id)
        except Exception as ex:
            raise DatastoreError(f"Error deleting {repo.model_desc}") from ex


class IndexDefinition:
    def __init__(self, keys: Sequence[str | tuple[str, int]], **kwargs: Any) -> None:  # noqa: ANN401
        self.keys = keys
        self.props = kwargs

class _GuildRepository[T: GuildDbModel]:
    repository_map: dict[type[GuildDbModel], type["_GuildRepository"]] = {}
    model_desc: str
    collection_name: str
    model_type: type[T]

    def __init_subclass__(cls, collection: str, model_desc: str) -> None:
        cls.model_desc = model_desc
        cls.collection_name = collection
        new_var = cls.__orig_bases__[0]  # type: ignore[attr-defined]
        cls.model_type = get_args(new_var)[0]
        _GuildRepository.repository_map[cls.model_type] = cls

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._db = db
        self._collection = db[self.collection_name]
        self._converter = make_db_converter()

    async def insert(self, obj: T) -> ObjectId:
        try:
            doc = self._converter.unstructure(obj)
            result = await self._collection.insert_one(doc)
        except pymongo.errors.DuplicateKeyError as ex:
            raise DuplicateKeyError() from ex
        except Exception as ex:
            raise DatastoreError(f"Error inserting {self.model_desc}") from ex
        else:
            return cast(ObjectId, result.inserted_id)

    async def list_all(self, guild_id: int, *, sort: str | None = None) -> list[T]:
        try:
            cursor = self._collection.find({"guild_id": {"$eq": guild_id}})
            if sort:
                cursor.sort(sort)
            result = [self._converter.structure(doc, self.model_type) for doc in await cursor.to_list(length=100)]
        except Exception as ex:
            raise DatastoreError(f"Error reading {self.model_desc}") from ex
        else:
            return result

    async def find_one(self, guild_id: int, attr_name: str, attr_value: Any) -> T | None:  # noqa: ANN401
        try:
            doc = await self._collection.find_one({"guild_id": {"$eq": guild_id}, attr_name: {"$eq": attr_value}})
            result = self._converter.structure(doc, self.model_type) if doc else None
        except Exception as ex:
            raise DatastoreError(f"Error reading {self.model_desc}") from ex
        else:
            return result

    async def delete(self, doc_id: ObjectId) -> None:
        try:
            await self._collection.delete_one({"_id": {"$eq": doc_id}})
        except Exception as ex:
            raise DatastoreError("Error deleting {self.model_desc}") from ex

    @classmethod
    def get_indexes(cls) -> Iterable[IndexDefinition]:
        return
        yield


class _GuildServerRepository(
    _GuildRepository[GuildServer],
    collection="servers",
    model_desc="guild server",
):
    @classmethod
    def get_indexes(cls) -> Iterable[IndexDefinition]:
        yield IndexDefinition(
            keys=[("guild_id", pymongo.ASCENDING), ("label", pymongo.ASCENDING)],
            name="guild_servers_by_label",
            unique=True,
        )
        yield IndexDefinition(
            keys=[("guild_id", pymongo.ASCENDING), ("crcon_details.api_url", pymongo.ASCENDING)],
            name="guild_servers_by_url",
            unique=True,
        )


class _GuildPlayerGroupRepository(
    _GuildRepository[GuildPlayerGroup],
    collection="player_groups",
    model_desc="player group",
):
    @classmethod
    def get_indexes(cls) -> Iterable[IndexDefinition]:
        yield IndexDefinition(
            keys=[("guild_id", pymongo.ASCENDING), ("label", pymongo.ASCENDING)],
            name="player_groups_by_label",
            unique=True,
        )
