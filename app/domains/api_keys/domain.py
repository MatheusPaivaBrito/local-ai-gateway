from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ApiKeyIdentity:
    id: int
    name: str
    key_prefix: str
    key_hash: str
    is_active: bool
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
