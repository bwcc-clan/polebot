"""Configuration for the application."""

import environ


@environ.config(prefix="APP")
class AppConfig:
    """Configuration for the application."""

    max_websocket_connection_attempts: int = environ.var(
        0, help="The maximum number of attempts to connect to a websocket.",
    )

    discord_token: str = environ.var(help="The token for the Discord bot.")
    discord_owner_id: int = environ.var(help="The ID of the Discord bot owner.")

    @environ.config
    class MongoConfig:
        """Configuration for the MongoDB connection."""

        connection_string: str = environ.var(help="The connection string for MongoDB.")
        db_name: str = environ.var("The name of the database to use in MongoDB.")

    mongodb: MongoConfig = environ.group(MongoConfig)
