from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from jugnu.profile import ScrapeProfile


class ProfileStore:
    """Persist and load ScrapeProfiles from a local directory."""

    def __init__(self, directory: str | Path = ".jugnu/profiles") -> None:
        self._dir = Path(directory)

    def _path(self, url_pattern: str) -> Path:
        import hashlib  # noqa: PLC0415

        key = hashlib.sha256(url_pattern.encode()).hexdigest()[:16]
        return self._dir / f"{key}.json"

    def save(self, profile: ScrapeProfile) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._path(profile.url_pattern)
            path.write_text(json.dumps(profile.model_dump(mode="json"), indent=2))
        except Exception:  # noqa: BLE001
            pass

    def load(self, url_pattern: str) -> Optional[ScrapeProfile]:
        try:
            path = self._path(url_pattern)
            if not path.exists():
                return None
            data = json.loads(path.read_text())
            return ScrapeProfile.model_validate(data)
        except Exception:  # noqa: BLE001
            return None

    def delete(self, url_pattern: str) -> None:
        try:
            self._path(url_pattern).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass

    def list_all(self) -> list[ScrapeProfile]:
        profiles: list[ScrapeProfile] = []
        try:
            for p in self._dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text())
                    profiles.append(ScrapeProfile.model_validate(data))
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            pass
        return profiles
