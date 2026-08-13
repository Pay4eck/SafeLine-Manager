"""Single source of truth for user-visible SafeLine product metadata."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


_BRAND_FILE = Path(__file__).with_name("brand.json")


@dataclass(frozen=True, slots=True)
class Brand:
    product_name: str
    full_name: str
    manager_name: str
    version: str
    description: str
    repository_url: str
    upstream_name: str
    upstream_repository_url: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _load_brand() -> Brand:
    with _BRAND_FILE.open(encoding="utf-8") as brand_file:
        return Brand(**json.load(brand_file))


BRAND = _load_brand()
