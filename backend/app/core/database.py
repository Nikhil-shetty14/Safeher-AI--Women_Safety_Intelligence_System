from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from loguru import logger

client: AsyncIOMotorClient = None


def _create_motor_client() -> AsyncIOMotorClient:
    """Create a tuned, memory-efficient AsyncIOMotorClient."""
    return AsyncIOMotorClient(
        settings.MONGODB_URL,
        maxPoolSize=10,
        minPoolSize=1,
        maxIdleTimeMS=30000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
        serverSelectionTimeoutMS=5000,
        waitQueueTimeoutMS=5000,
        tlsAllowInvalidCertificates=True,
    )


async def connect_db():
    global client
    try:
        if client is None:
            client = _create_motor_client()
        await client.admin.command("ping")
        logger.info("Connected to MongoDB Atlas successfully")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}. Motor will automatically retry on the next request.")
        # DO NOT set client = None. Let Motor retry.


async def close_db():
    global client
    if client:
        client.close()
        client = None
        logger.info("MongoDB connection closed")


def get_database():
    global client
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        if client is not None:
            io_loop = getattr(client, "io_loop", None) or getattr(client, "_io_loop", None)
            if io_loop is not None and (io_loop.is_closed() or io_loop != loop):
                client = None
    except RuntimeError:
        pass
    except Exception as e:
        logger.debug(f"Event loop verification note: {e}")

    if client is None:
        client = _create_motor_client()
    return client[settings.DATABASE_NAME]


def get_collection(collection_name: str):
    db = get_database()
    return db[collection_name]
