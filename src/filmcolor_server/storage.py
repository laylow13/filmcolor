from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from filmcolor_core.models import (
    EngineSettings,
    FrameSidecar,
    FrameStatus,
    PipelineSettings,
    RollMetadata,
)
from filmcolor_core.sidecar import (
    read_frame_sidecar,
    read_roll_metadata,
    write_frame_sidecar,
    write_roll_metadata,
)


SUPPORTED_INPUT_EXTENSIONS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".jpg",
    ".jpeg",
    ".nef",
    ".orf",
    ".png",
    ".raf",
    ".rw2",
    ".tif",
    ".tiff",
}


class Workspace:
    def __init__(self, root: Path):
        self.root = root
        self.rolls_dir = root / "rolls"

    def import_roll(self, source_dir: Path, name: str) -> RollMetadata:
        source_dir = source_dir.resolve()
        if not source_dir.exists() or not source_dir.is_dir():
            raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

        roll_id = self._unique_roll_id(source_dir.name)
        roll_dir = self._roll_dir(roll_id)
        (roll_dir / "frames").mkdir(parents=True, exist_ok=True)
        (roll_dir / "previews").mkdir(parents=True, exist_ok=True)
        (roll_dir / "exports" / "tiff").mkdir(parents=True, exist_ok=True)
        (roll_dir / "exports" / "jpeg").mkdir(parents=True, exist_ok=True)
        (roll_dir / "logs").mkdir(parents=True, exist_ok=True)

        roll = RollMetadata.create(roll_id=roll_id, name=name, source_dir=source_dir)
        write_roll_metadata(roll_dir / "roll.json", roll)

        for source_path in sorted(source_dir.iterdir()):
            if source_path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
                continue
            frame_id = source_path.stem
            sidecar = FrameSidecar.create(
                frame_id=frame_id,
                source_path=source_path,
                sha256=_sha256(source_path),
            )
            write_frame_sidecar(self._frame_path(roll_id, frame_id), sidecar)

        return roll

    def list_rolls(self) -> list[RollMetadata]:
        if not self.rolls_dir.exists():
            return []
        return [read_roll_metadata(path) for path in sorted(self.rolls_dir.glob("*/roll.json"))]

    def get_roll(self, roll_id: str) -> RollMetadata:
        return read_roll_metadata(self._roll_dir(roll_id) / "roll.json")

    def list_frames(self, roll_id: str) -> list[FrameSidecar]:
        frames_dir = self._roll_dir(roll_id) / "frames"
        if not frames_dir.exists():
            return []
        return [read_frame_sidecar(path) for path in sorted(frames_dir.glob("*.xmp.json"))]

    def get_frame(self, roll_id: str, frame_id: str) -> FrameSidecar:
        return read_frame_sidecar(self._frame_path(roll_id, frame_id))

    def update_frame_pipeline(
        self,
        roll_id: str,
        frame_id: str,
        patch: dict[str, Any],
    ) -> FrameSidecar:
        sidecar = self.get_frame(roll_id, frame_id)
        data = sidecar.pipeline.model_dump(mode="json")
        _deep_merge(data, patch)
        sidecar.pipeline = PipelineSettings.model_validate(data)
        sidecar.status = FrameStatus.MANUALLY_ADJUSTED
        write_frame_sidecar(self._frame_path(roll_id, frame_id), sidecar)
        return sidecar

    def update_frame_engines(
        self,
        roll_id: str,
        frame_id: str,
        patch: dict[str, Any],
    ) -> FrameSidecar:
        sidecar = self.get_frame(roll_id, frame_id)
        data = sidecar.engines.model_dump(mode="json")
        _deep_merge(data, patch)
        sidecar.engines = EngineSettings.model_validate(data)
        sidecar.status = FrameStatus.MANUALLY_ADJUSTED
        write_frame_sidecar(self._frame_path(roll_id, frame_id), sidecar)
        return sidecar

    def preview_path(self, roll_id: str, frame_id: str) -> Path:
        return self._roll_dir(roll_id) / "previews" / f"{frame_id}.preview.webp"

    def _roll_dir(self, roll_id: str) -> Path:
        return self.rolls_dir / roll_id

    def _frame_path(self, roll_id: str, frame_id: str) -> Path:
        return self._roll_dir(roll_id) / "frames" / f"{frame_id}.xmp.json"

    def _unique_roll_id(self, source_name: str) -> str:
        base = _slug(source_name) or "roll"
        index = 1
        while True:
            roll_id = f"{base}-{index:03d}"
            if not self._roll_dir(roll_id).exists():
                return roll_id
            index += 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value: str) -> str:
    result = []
    for char in value.lower():
        if char.isalnum():
            result.append(char)
        elif result and result[-1] != "-":
            result.append("-")
    return "".join(result).strip("-")


def _deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
