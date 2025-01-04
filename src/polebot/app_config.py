"""Configuration for the application."""

import environ


@environ.config(prefix="APP")
class AppConfig:
    """Configuration for the application."""

    config_dir: str = environ.var(".config")

    @environ.config
    class MongoConfig:
        """Configuration for the MongoDB connection."""

        connection_string: str = environ.var("mongodb://localhost:27017/")
        db_name: str = environ.var("polebot")

    mongodb: MongoConfig = environ.group(MongoConfig)
