from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class DecodedImage:
    data: np.ndarray
    metadata: dict[str, str]


RAW_EXTENSIONS = {".3fr", ".arw", ".cr2", ".cr3", ".dng", ".nef", ".orf", ".raf", ".rw2"}


def decode_to_linear_rgb(path: Path) -> DecodedImage:
    suffix = path.suffix.lower()
    if suffix in RAW_EXTENSIONS:
        return _decode_rawpy(path)
    return _decode_pillow(path)


def _decode_pillow(path: Path) -> DecodedImage:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        array = np.asarray(rgb).astype(np.float32) / 255.0
    linear = np.power(np.clip(array, 0.0, 1.0), 2.2).astype(np.float32)
    return DecodedImage(data=linear, metadata={"decoder": "pillow", "path": path.as_posix()})


def _decode_rawpy(path: Path) -> DecodedImage:
    try:
        import rawpy
    except ImportError as exc:
        raise RuntimeError("RAW decoding requires the optional raw extra: uv sync --extra raw") from exc

    with rawpy.imread(str(path)) as raw:
        rgb16 = raw.postprocess(
            output_bps=16,
            no_auto_bright=True,
            use_camera_wb=True,
            gamma=(1, 1),
        )
    linear = rgb16.astype(np.float32) / 65535.0
    return DecodedImage(
        data=np.clip(linear, 0.0, 1.0),
        metadata={"decoder": "rawpy", "path": path.as_posix()},
    )
