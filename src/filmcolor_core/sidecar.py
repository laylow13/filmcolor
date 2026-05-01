from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from filmcolor_core.models import FrameSidecar, RollMetadata

ModelT = TypeVar("ModelT", bound=BaseModel)


def _read_json_model(path: Path, model: type[ModelT]) -> ModelT:
    data = json.loads(path.read_text(encoding="utf-8"))
    return model.model_validate(data)


def _write_json_model(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        value.model_dump_json(indent=2),
        encoding="utf-8",
    )


def read_roll_metadata(path: Path) -> RollMetadata:
    return _read_json_model(path, RollMetadata)


def write_roll_metadata(path: Path, roll: RollMetadata) -> None:
    _write_json_model(path, roll)


def read_frame_sidecar(path: Path) -> FrameSidecar:
    return _read_json_model(path, FrameSidecar)


def write_frame_sidecar(path: Path, sidecar: FrameSidecar) -> None:
    _write_json_model(path, sidecar)
