import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import Database
from app.core.security import hash_api_key
from app.domains.api_keys.persistence import ApiKeyRecord


async def main(raw_key: str) -> None:
    database = Database(get_settings())
    try:
        async with database.sessions() as session:
            api_key = await session.scalar(
                select(ApiKeyRecord).where(ApiKeyRecord.key_hash == hash_api_key(raw_key))
            )
            if api_key is None:
                raise SystemExit("API key not found")
            api_key.is_active = False
            api_key.revoked_at = datetime.now(UTC)
            await session.commit()
            print(f"revoked: {api_key.key_prefix}")
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Revoke a Local AI Gateway API key")
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.key))
