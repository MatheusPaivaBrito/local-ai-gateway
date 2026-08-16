import argparse
import asyncio

from app.core.config import get_settings
from app.core.database import Database
from app.domains.api_keys.repository import SqlAlchemyApiKeyRepository
from app.domains.api_keys.service import ApiKeyService


async def main(name: str) -> None:
    database = Database(get_settings())
    service = ApiKeyService(SqlAlchemyApiKeyRepository())
    try:
        async with database.sessions() as session:
            _, raw_key = await service.create(session, name=name)
            print(raw_key)
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a Local AI Gateway API key")
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.name))
