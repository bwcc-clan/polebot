"""Configuration classes for the application."""

import datetime as dt
import logging

from attrs import define, field, frozen, validators
from bson import ObjectId

from crcon.server_connection_details import ServerConnectionDetails

_logger = logging.getLogger(__name__)


@frozen(kw_only=True)
class EnvironmentGroup:
    """Represents a group of environments and their parameters."""

    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    environments: list[str] = field(factory=list)


@frozen(kw_only=True)
class MapGroup:
    """Represents a group of maps and their parameters."""

    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_decay: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    maps: list[str] = field(factory=list)


@frozen(kw_only=True)
class WeightingParameters:
    """Parameters for map and environment weighting."""

    groups: dict[str, MapGroup]
    environments: dict[str, EnvironmentGroup]


@frozen
class VipInfo:
    player_id: str
    player_name: str
    vip_expiry: dt.datetime | None


UNSAVED_SENTINEL = -1


@define(kw_only=True)
class DbModel:
    _id: ObjectId = field(factory=ObjectId)
    _v: int = field(default=UNSAVED_SENTINEL)
    _created_utc: dt.datetime | None = field(default=None)
    _modified_utc: dt.datetime | None = field(default=None)

    @property
    def id(self) -> ObjectId:
        return self._id

    @property
    def db_version(self) -> int:
        return self._v

    @property
    def created_date_utc(self) -> dt.datetime:
        if not self._created_utc:
            raise ValueError("Created date not set - has the document been saved?")
        return self._created_utc

    @property
    def modified_date_utc(self) -> dt.datetime:
        if not self._modified_utc:
            raise ValueError("Modified date not set - has the document been saved?")
        return self._modified_utc


@define(kw_only=True)
class GuildServer(DbModel):
    guild_id: int
    label: str = field(validator=[validators.min_len(1), validators.max_len(10)])
    name: str = field(validator=[validators.min_len(1), validators.max_len(100)])
    crcon_details: ServerConnectionDetails
    enable_votemap: bool = field(default=False)
    weighting_parameters: WeightingParameters | None = field(default=None)


@define(kw_only=True)
class GuildPlayerGroup(DbModel):
    guild_id: int
    label: str = field(validator=[validators.min_len(1), validators.max_len(10)])
    selector: str = field(validator=[validators.min_len(1), validators.max_len(100)])
