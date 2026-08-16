from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class InstalledModel:
    name: str
    size: int | None = None
    digest: str | None = None
    modified_at: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    running: bool = False


@dataclass(frozen=True, slots=True)
class RegistryModel:
    name: str
    description: str = ""
    url: str | None = None


@dataclass(frozen=True, slots=True)
class RegistryModelTag:
    name: str
    tag: str
    size: str | None = None
    size_bytes: int | None = None
    digest: str | None = None
    context_window: str | None = None
    input_types: tuple[str, ...] = ()
    updated: str | None = None
    url: str | None = None


class ModelNotInstalledError(LookupError):
    pass
