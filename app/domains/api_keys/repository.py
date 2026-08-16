from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import api_key_prefix, verify_api_key
from app.domains.api_keys.domain import ApiKeyIdentity
from app.domains.api_keys.persistence import ApiKeyRecord


def _to_domain(record: ApiKeyRecord) -> ApiKeyIdentity:
    return ApiKeyIdentity(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        key_hash=record.key_hash,
        is_active=record.is_active,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
    )


class SqlAlchemyApiKeyRepository:
    async def add(self, session: AsyncSession, record: ApiKeyRecord) -> ApiKeyIdentity:
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return _to_domain(record)

    async def find_valid(self, session: AsyncSession, raw_key: str) -> ApiKeyIdentity | None:
        prefix = api_key_prefix(raw_key)
        result = await session.execute(
            select(ApiKeyRecord).where(
                ApiKeyRecord.key_prefix == prefix,
                ApiKeyRecord.is_active.is_(True),
            )
        )
        for candidate in result.scalars().all():
            if verify_api_key(raw_key, candidate.key_hash):
                candidate.last_used_at = datetime.now(UTC)
                await session.commit()
                return _to_domain(candidate)
        return None

    async def by_hash(self, session: AsyncSession, key_hash: str) -> ApiKeyRecord | None:
        return await session.scalar(select(ApiKeyRecord).where(ApiKeyRecord.key_hash == key_hash))

    async def revoke_named_active(self, session: AsyncSession, name: str) -> None:
        await session.execute(
            update(ApiKeyRecord)
            .where(ApiKeyRecord.name == name, ApiKeyRecord.is_active.is_(True))
            .values(is_active=False, revoked_at=datetime.now(UTC))
        )
        await session.commit()
