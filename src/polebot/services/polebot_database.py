"""Polebot database layer."""

import datetime as dt
from collections.abc import Iterable, Sequence
from typing import Any, get_args

import pymongo
import pymongo.errors
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..app_config import AppConfig
from ..exceptions import ConcurrencyError, DatastoreError, DuplicateKeyError
from ..models import UNSAVED_SENTINEL, DbModel, GuildPlayerGroup, GuildServer
from .cattrs_helpers import make_db_converter


class PolebotDatabase:
    """Data store for CRCON server details."""

    def __init__(self, app_config: AppConfig, db: AsyncIOMotorDatabase) -> None:
        """Initialises the configuration repository."""
        self._app_config = app_config
        self._db = db
        self._converter = make_db_converter()

    async def initialize(self) -> None:
        for repo in _EntityRepository.repository_map.values():
            for index in repo.get_indexes():
                await self._db[repo.collection_name].create_index(index.keys, **index.props)

    async def insert[T: DbModel](self, obj: T) -> T:
        cls = type(obj)
        repo_type: type[_EntityRepository[T]] | None = _EntityRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        return await repo.insert(obj)

    async def update[T: DbModel](self, obj: T) -> T:
        cls = type(obj)
        repo_type: type[_EntityRepository[T]] | None = _EntityRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        return await repo.update(obj)

    async def fetch_all[T: DbModel](self, cls: type[T], guild_id: int | None, *, sort: str | None = None) -> list[T]:
        repo_type: type[_EntityRepository[T]] | None = _EntityRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        try:
            docs = await repo.fetch_all(guild_id, sort=sort)
        except Exception as ex:
            raise DatastoreError(f"Error reading {repo.model_desc} list") from ex
        else:
            return docs

    async def find_one[T: DbModel](self, cls: type[T], guild_id: int, attr_name: str, attr_value: Any) -> T | None:  # noqa: ANN401
        repo_type: type[_EntityRepository[T]] | None = _EntityRepository.repository_map.get(cls, None)
        if not repo_type:
            raise RuntimeError(f"Repository not found for type {cls.__name__}")
        repo = repo_type(self._db)
        return await repo.find_one(guild_id, attr_name=attr_name, attr_value=attr_value)

    async def delete[T: DbModel](self, cls: type[T], doc_id: ObjectId) -> None:
        repo_type = _EntityRepository.repository_map.get(cls, None)
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


class _EntityRepository[T: DbModel]:
    repository_map: dict[type[DbModel], type["_EntityRepository"]] = {}
    model_desc: str
    collection_name: str
    model_type: type[T]

    def __init_subclass__(cls, collection: str, model_desc: str) -> None:
        cls.model_desc = model_desc
        cls.collection_name = collection
        new_var = cls.__orig_bases__[0]  # type: ignore[attr-defined]
        cls.model_type = get_args(new_var)[0]
        _EntityRepository.repository_map[cls.model_type] = cls

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._db = db
        self._collection = db[self.collection_name]
        self._converter = make_db_converter()

    async def insert(self, obj: T) -> T:
        if obj._v != UNSAVED_SENTINEL:
            raise DatastoreError("Object has previously been saved")
        obj._v = 1
        obj._created_utc = obj._modified_utc = dt.datetime.now(dt.UTC)
        try:
            doc = self._converter.unstructure(obj)
            result = await self._collection.insert_one(doc)
        except pymongo.errors.DuplicateKeyError as ex:
            raise DuplicateKeyError() from ex
        except Exception as ex:
            raise DatastoreError(f"Error inserting {self.model_desc}") from ex
        else:
            obj._id = result.inserted_id
            return obj

    async def update(self, obj: T) -> T:
        if obj._v == UNSAVED_SENTINEL:
            raise DatastoreError("Object has never been saved")
        current_version = obj._v
        obj._v += 1
        obj._modified_utc = dt.datetime.now(dt.UTC)
        try:
            doc = self._converter.unstructure(obj)
            result = await self._collection.replace_one({"_id": {"$eq": obj.id}, "_v": {"$eq": current_version}}, doc)
        except Exception as ex:
            raise DatastoreError(f"Error updating {self.model_desc}") from ex
        else:
            if result.modified_count == 0:
                raise ConcurrencyError(current_version)
            return obj

    async def fetch_all(self, guild_id: int | None, *, sort: str | None = None) -> list[T]:
        try:
            search_params = {"guild_id": {"$eq": guild_id}} if guild_id else {}
            cursor = self._collection.find(search_params)
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
    _EntityRepository[GuildServer],
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
    _EntityRepository[GuildPlayerGroup],
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
