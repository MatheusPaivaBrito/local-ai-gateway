from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import api_key_prefix, generate_api_key, hash_api_key
from app.domains.api_keys.domain import ApiKeyIdentity
from app.domains.api_keys.persistence import ApiKeyRecord
from app.domains.api_keys.repository import SqlAlchemyApiKeyRepository


class ApiKeyService:
    def __init__(self, repository: SqlAlchemyApiKeyRepository) -> None:
        self.repository = repository

    async def create(self, session: AsyncSession, *, name: str) -> tuple[ApiKeyIdentity, str]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("API key name cannot be empty")

        raw_key = generate_api_key()
        identity = await self.repository.add(
            session,
            ApiKeyRecord(
                name=clean_name,
                key_prefix=api_key_prefix(raw_key),
                key_hash=hash_api_key(raw_key),
                is_active=True,
            ),
        )
        return identity, raw_key

    async def authenticate(self, session: AsyncSession, raw_key: str) -> ApiKeyIdentity | None:
        return await self.repository.find_valid(session, raw_key)

    async def ensure_bootstrap_key(
        self,
        session: AsyncSession,
        *,
        raw_key: str | None,
        name: str,
    ) -> None:
        if not raw_key:
            return
        key_hash = hash_api_key(raw_key)
        existing = await self.repository.by_hash(session, key_hash)
        if existing is None:
            await self.repository.add(
                session,
                ApiKeyRecord(
                    name=name,
                    key_prefix=api_key_prefix(raw_key),
                    key_hash=key_hash,
                    is_active=True,
                ),
            )
            return
        if not existing.is_active or existing.revoked_at is not None:
            existing.is_active = True
            existing.revoked_at = None
            await session.commit()

    async def rotate_local_ui_key(
        self,
        session: AsyncSession,
        *,
        name: str,
        enabled: bool,
    ) -> str | None:
        await self.repository.revoke_named_active(session, name)
        if not enabled:
            return None
        _, raw_key = await self.create(session, name=name)
        return raw_key
