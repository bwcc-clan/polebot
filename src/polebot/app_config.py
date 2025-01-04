"""Configuration for the application."""

import environ


@environ.config(prefix="APP")
class AppConfig:
    """Configuration for the application."""

    config_dir: str = environ.var(".config")

    max_websocket_connection_attempts: int = environ.var(
        0, help="The maximum number of attempts to connect to a websocket.",
    )

    @environ.config
    class MongoConfig:
        """Configuration for the MongoDB connection."""

        connection_string: str = environ.var("mongodb://localhost:27017/", help="The connection string for MongoDB.")
        db_name: str = environ.var("polebot", help="The name of the database to use in MongoDB.")

    mongodb: MongoConfig = environ.group(MongoConfig)
