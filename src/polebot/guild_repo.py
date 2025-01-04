"""Configuration repository for Polebot."""
from motor.motor_asyncio import AsyncIOMotorDatabase

from .app_config import AppConfig


class GuildRepository:
    """Data store for server configuration."""
    def __init__(self, app_config: AppConfig, db: AsyncIOMotorDatabase) -> None:
        """Initialises the configuration repository."""
        self._app_config = app_config
        self._db = db

