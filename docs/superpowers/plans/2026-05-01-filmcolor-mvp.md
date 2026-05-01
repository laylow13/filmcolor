# Filmcolor MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable local MVP for color negative RAW conversion, sidecar persistence, preview rendering, and a modern web workbench.

**Architecture:** Use a Python `src/` monorepo with a standalone `filmcolor_core` package and a FastAPI `filmcolor_server` package. Use a Vite React TypeScript frontend in `web/` that talks to the local API and renders a roll-oriented light-table workbench.

**Tech Stack:** Python 3.12+ managed by uv, pytest, numpy, pillow, tifffile, rawpy adapter boundary, pydantic, FastAPI, uvicorn, React, TypeScript, Vite, Vitest.

---

## Scope

This plan implements the first vertical slice of the confirmed design:

- Core image pipeline for array-based tests and image-file rendering.
- Sidecar and roll metadata models.
- Local workspace storage.
- FastAPI endpoints for roll import, frame listing, pipeline patching, preview rendering, and job inspection.
- Web MVP for roll list, frame grid, preview, basic parameter panel, and output style switching.
- Tests for core math, storage, API behavior, and frontend rendering.

This plan intentionally keeps true camera RAW decoding behind an adapter. The first implementation supports tested synthetic arrays and common image fixtures through Pillow, then adds a `rawpy` adapter hook with clear failure behavior when `rawpy` or an unsupported RAW file is unavailable.

## File Structure

Create or modify these files:

```text
D:/filmcolor/
  pyproject.toml
  uv.lock
  README.md
  src/
    filmcolor_core/
      __init__.py
      models.py
      pipeline.py
      raw.py
      render.py
      sidecar.py
    filmcolor_server/
      __init__.py
      app.py
      jobs.py
      storage.py
  tests/
    core/
      test_pipeline.py
      test_sidecar.py
    server/
      test_api.py
      test_storage.py
  web/
    package.json
    index.html
    tsconfig.json
    tsconfig.node.json
    vite.config.ts
    src/
      App.tsx
      api.ts
      main.tsx
      styles.css
      types.ts
      App.test.tsx
```

Responsibilities:

- `filmcolor_core.models`: shared pydantic models for roll, frame, pipeline, samples, jobs, and exports.
- `filmcolor_core.pipeline`: deterministic numeric operations for negative inversion, orange-mask estimation, balancing, and tone styles.
- `filmcolor_core.raw`: input decoding adapter with image-file fallback and optional RAW support.
- `filmcolor_core.render`: preview and export rendering helpers.
- `filmcolor_core.sidecar`: JSON serialization helpers for roll and frame sidecars.
- `filmcolor_server.storage`: workspace layout, roll import, frame sidecar updates, and preview paths.
- `filmcolor_server.jobs`: small in-process job registry.
- `filmcolor_server.app`: FastAPI app and API routes.
- `web/src/api.ts`: typed frontend API calls.
- `web/src/App.tsx`: the MVP workbench UI.
- `web/src/styles.css`: Modern Darkroom plus Light Table styling.

---

### Task 1: Python Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/filmcolor_core/__init__.py`
- Create: `src/filmcolor_server/__init__.py`

- [ ] **Step 1: Create the failing import smoke test**

Create `tests/core/test_pipeline.py` with this initial content:

```python
def test_core_package_imports():
    import filmcolor_core

    assert filmcolor_core.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run:

```powershell
uv run pytest tests/core/test_pipeline.py::test_core_package_imports -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'filmcolor_core'`.

- [ ] **Step 3: Add Python package configuration**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "filmcolor"
version = "0.1.0"
description = "Local color negative inversion and orange-mask correction workbench"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "numpy>=1.26",
  "pillow>=10.0",
  "pydantic>=2.7",
  "python-multipart>=0.0.9",
  "tifffile>=2024.0",
  "uvicorn[standard]>=0.30"
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27",
  "pytest>=8.0",
  "pytest-cov>=5.0",
  "ruff>=0.6"
]
raw = [
  "rawpy>=0.21"
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

Create `src/filmcolor_core/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/filmcolor_server/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `README.md`:

```markdown
# Filmcolor

Filmcolor is a local color negative processing workbench. It keeps original captures unchanged, stores processing decisions in JSON sidecars, and renders previews or exports from reproducible pipeline parameters.

## Development

Install Python dependencies:

```powershell
uv sync --extra dev
```

Run tests:

```powershell
uv run pytest
```
```

- [ ] **Step 4: Install editable dev dependencies**

Run:

```powershell
uv sync --extra dev
```

Expected: command completes and reports `Successfully installed filmcolor-0.1.0` or equivalent editable install output.

- [ ] **Step 5: Run the smoke test to verify it passes**

Run:

```powershell
uv run pytest tests/core/test_pipeline.py::test_core_package_imports -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml uv.lock README.md src/filmcolor_core/__init__.py src/filmcolor_server/__init__.py tests/core/test_pipeline.py
git commit -m "chore: scaffold python packages"
```

---

### Task 2: Shared Models and Sidecar Serialization

**Files:**
- Create: `src/filmcolor_core/models.py`
- Create: `src/filmcolor_core/sidecar.py`
- Create: `tests/core/test_sidecar.py`

- [ ] **Step 1: Write failing model and sidecar tests**

Create `tests/core/test_sidecar.py`:

```python
from pathlib import Path

from filmcolor_core.models import FrameSidecar, OutputStyle, RollMetadata
from filmcolor_core.sidecar import read_frame_sidecar, read_roll_metadata, write_frame_sidecar, write_roll_metadata


def test_roll_metadata_round_trips(tmp_path: Path):
    roll = RollMetadata.create(
        roll_id="2026-05-01-roll-001",
        name="E100 Studio Test",
        source_dir=Path("D:/film/raw/E100-test"),
    )

    path = tmp_path / "roll.json"
    write_roll_metadata(path, roll)
    loaded = read_roll_metadata(path)

    assert loaded.id == "2026-05-01-roll-001"
    assert loaded.defaults.output_style == OutputStyle.FAITHFUL
    assert loaded.source_dir == "D:/film/raw/E100-test"


def test_frame_sidecar_separates_auto_and_user_values(tmp_path: Path):
    sidecar = FrameSidecar.create(
        frame_id="IMG_0001",
        source_path=Path("D:/film/raw/E100-test/IMG_0001.CR3"),
        sha256="abc123",
    )
    sidecar.pipeline.mask.auto.rgb_gain = [1.08, 0.97, 0.91]
    sidecar.pipeline.mask.auto.confidence = 0.82
    sidecar.pipeline.mask.samples.film_base = [[120, 840], [134, 842]]

    path = tmp_path / "IMG_0001.xmp.json"
    write_frame_sidecar(path, sidecar)
    loaded = read_frame_sidecar(path)

    assert loaded.frame_id == "IMG_0001"
    assert loaded.pipeline.mask.auto.rgb_gain == [1.08, 0.97, 0.91]
    assert loaded.pipeline.mask.samples.film_base == [[120, 840], [134, 842]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/core/test_sidecar.py -v
```

Expected: FAIL with `ModuleNotFoundError` or import errors for `filmcolor_core.models`.

- [ ] **Step 3: Implement pydantic models**

Create `src/filmcolor_core/models.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class OutputStyle(StrEnum):
    FAITHFUL = "faithful"
    NEUTRAL = "neutral"
    SHARE = "share"


class FrameStatus(StrEnum):
    UNPROCESSED = "unprocessed"
    PROCESSING = "processing"
    AUTO_PROCESSED = "auto_processed"
    MANUALLY_ADJUSTED = "manually_adjusted"
    EXPORTED = "exported"
    FAILED = "failed"
    MISSING = "missing"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class RollDefaults(BaseModel):
    film_profile: str = "generic_color_negative"
    output_style: OutputStyle = OutputStyle.FAITHFUL
    color_space: str = "sRGB"


class RollMetadata(BaseModel):
    id: str
    name: str
    source_dir: str
    created_at: str
    defaults: RollDefaults = Field(default_factory=RollDefaults)

    @classmethod
    def create(cls, roll_id: str, name: str, source_dir: Path) -> "RollMetadata":
        return cls(
            id=roll_id,
            name=name,
            source_dir=source_dir.as_posix(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class SourceMetadata(BaseModel):
    path: str
    sha256: str
    camera: str | None = None
    lens: str | None = None
    captured_at: str | None = None


class RawSettings(BaseModel):
    white_balance: str = "camera"
    black_level_mode: str = "metadata"


class InversionSettings(BaseModel):
    enabled: bool = True
    method: str = "linear_density"


class MaskAutoEstimate(BaseModel):
    rgb_gain: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    confidence: float = 0.0


class MaskSamples(BaseModel):
    film_base: list[list[int]] = Field(default_factory=list)
    gray: list[list[int]] = Field(default_factory=list)
    white: list[list[int]] = Field(default_factory=list)


class MaskSettings(BaseModel):
    auto: MaskAutoEstimate = Field(default_factory=MaskAutoEstimate)
    samples: MaskSamples = Field(default_factory=MaskSamples)


class ToneSettings(BaseModel):
    style: OutputStyle = OutputStyle.FAITHFUL
    exposure: float = 0.0
    contrast: float = 0.12
    black_point: float = 0.004
    white_point: float = 0.985


class PipelineSettings(BaseModel):
    version: str = "0.1.0"
    raw: RawSettings = Field(default_factory=RawSettings)
    inversion: InversionSettings = Field(default_factory=InversionSettings)
    mask: MaskSettings = Field(default_factory=MaskSettings)
    tone: ToneSettings = Field(default_factory=ToneSettings)


class ExportRecord(BaseModel):
    format: str
    path: str
    created_at: str
    color_space: str


class FrameSidecar(BaseModel):
    frame_id: str
    status: FrameStatus = FrameStatus.UNPROCESSED
    source: SourceMetadata
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    exports: list[ExportRecord] = Field(default_factory=list)
    error: str | None = None

    @classmethod
    def create(cls, frame_id: str, source_path: Path, sha256: str) -> "FrameSidecar":
        return cls(
            frame_id=frame_id,
            source=SourceMetadata(path=source_path.as_posix(), sha256=sha256),
        )


class JobRecord(BaseModel):
    id: str
    kind: str
    status: JobStatus
    message: str = ""
    progress: float = 0.0
```

- [ ] **Step 4: Implement sidecar JSON helpers**

Create `src/filmcolor_core/sidecar.py`:

```python
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
```

- [ ] **Step 5: Run sidecar tests**

Run:

```powershell
uv run pytest tests/core/test_sidecar.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/filmcolor_core/models.py src/filmcolor_core/sidecar.py tests/core/test_sidecar.py
git commit -m "feat: add roll and frame sidecars"
```

---

### Task 3: Core Pipeline Math

**Files:**
- Create: `src/filmcolor_core/pipeline.py`
- Modify: `tests/core/test_pipeline.py`

- [ ] **Step 1: Replace pipeline tests with numeric behavior tests**

Replace `tests/core/test_pipeline.py` with:

```python
import numpy as np

from filmcolor_core import __version__
from filmcolor_core.models import OutputStyle, PipelineSettings
from filmcolor_core.pipeline import (
    apply_output_style,
    estimate_mask_gain,
    invert_linear,
    normalize_black_white,
    render_pipeline_array,
)


def test_core_package_imports():
    assert __version__ == "0.1.0"


def test_normalize_black_white_clips_to_unit_range():
    image = np.array([[[0.0, 0.5, 1.0], [1.5, -0.5, 0.25]]], dtype=np.float32)

    result = normalize_black_white(image, black_point=0.0, white_point=1.0)

    assert result.min() == 0.0
    assert result.max() == 1.0


def test_invert_linear_keeps_unit_range():
    image = np.array([[[0.1, 0.25, 0.9]]], dtype=np.float32)

    result = invert_linear(image)

    np.testing.assert_allclose(result, np.array([[[0.9, 0.75, 0.1]]], dtype=np.float32))


def test_estimate_mask_gain_uses_samples_when_present():
    image = np.ones((4, 4, 3), dtype=np.float32)
    image[1, 1] = [0.5, 1.0, 2.0]

    estimate = estimate_mask_gain(image, film_base_samples=[[1, 1]])

    np.testing.assert_allclose(estimate.rgb_gain, [2.0, 1.0, 0.5], rtol=1e-5)
    assert estimate.confidence == 1.0


def test_estimate_mask_gain_falls_back_to_gray_world():
    image = np.zeros((2, 2, 3), dtype=np.float32)
    image[:, :] = [0.5, 1.0, 2.0]

    estimate = estimate_mask_gain(image, film_base_samples=[])

    np.testing.assert_allclose(estimate.rgb_gain, [2.0, 1.0, 0.5], rtol=1e-5)
    assert estimate.confidence == 0.55


def test_output_styles_have_different_contrast_strengths():
    ramp = np.linspace(0.2, 0.8, 6, dtype=np.float32).reshape(1, 2, 3)

    faithful = apply_output_style(ramp, OutputStyle.FAITHFUL, exposure=0.0, contrast=0.0)
    share = apply_output_style(ramp, OutputStyle.SHARE, exposure=0.0, contrast=0.0)

    assert share.std() > faithful.std()


def test_render_pipeline_array_returns_uint8_preview():
    image = np.full((8, 8, 3), 0.25, dtype=np.float32)
    settings = PipelineSettings()

    rendered, diagnostics = render_pipeline_array(image, settings, max_size=4)

    assert rendered.dtype == np.uint8
    assert rendered.shape == (4, 4, 3)
    assert diagnostics["mask_confidence"] == 0.55
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/core/test_pipeline.py -v
```

Expected: FAIL with import errors for `filmcolor_core.pipeline`.

- [ ] **Step 3: Implement pipeline operations**

Create `src/filmcolor_core/pipeline.py`:

```python
from __future__ import annotations

import numpy as np
from PIL import Image

from filmcolor_core.models import MaskAutoEstimate, OutputStyle, PipelineSettings


def normalize_black_white(image: np.ndarray, black_point: float, white_point: float) -> np.ndarray:
    denominator = max(white_point - black_point, 1e-6)
    return np.clip((image.astype(np.float32) - black_point) / denominator, 0.0, 1.0)


def invert_linear(image: np.ndarray) -> np.ndarray:
    return np.clip(1.0 - image.astype(np.float32), 0.0, 1.0)


def estimate_mask_gain(
    image: np.ndarray,
    film_base_samples: list[list[int]],
) -> MaskAutoEstimate:
    linear = np.clip(image.astype(np.float32), 1e-6, 1.0)
    if film_base_samples:
        sampled = []
        height, width = linear.shape[:2]
        for x, y in film_base_samples:
            if 0 <= x < width and 0 <= y < height:
                sampled.append(linear[y, x])
        if sampled:
            base = np.mean(np.stack(sampled), axis=0)
            gain = _neutralizing_gain(base)
            return MaskAutoEstimate(rgb_gain=gain.tolist(), confidence=1.0)

    mean_rgb = linear.reshape(-1, 3).mean(axis=0)
    gain = _neutralizing_gain(mean_rgb)
    return MaskAutoEstimate(rgb_gain=gain.tolist(), confidence=0.55)


def apply_channel_gain(image: np.ndarray, rgb_gain: list[float]) -> np.ndarray:
    gain = np.array(rgb_gain, dtype=np.float32).reshape(1, 1, 3)
    return np.clip(image.astype(np.float32) * gain, 0.0, 1.0)


def apply_output_style(
    image: np.ndarray,
    style: OutputStyle,
    exposure: float,
    contrast: float,
) -> np.ndarray:
    exposed = np.clip(image.astype(np.float32) * (2.0**exposure), 0.0, 1.0)
    if style == OutputStyle.NEUTRAL:
        style_contrast = 0.92 + contrast
        saturation = 0.92
    elif style == OutputStyle.SHARE:
        style_contrast = 1.22 + contrast
        saturation = 1.12
    else:
        style_contrast = 1.02 + contrast
        saturation = 1.0

    contrasted = np.clip((exposed - 0.5) * style_contrast + 0.5, 0.0, 1.0)
    luminance = contrasted @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    saturated = luminance[:, :, None] + (contrasted - luminance[:, :, None]) * saturation
    return np.clip(saturated, 0.0, 1.0)


def render_pipeline_array(
    image: np.ndarray,
    settings: PipelineSettings,
    max_size: int | None = None,
) -> tuple[np.ndarray, dict[str, float]]:
    normalized = normalize_black_white(
        image,
        black_point=settings.tone.black_point,
        white_point=settings.tone.white_point,
    )
    inverted = invert_linear(normalized) if settings.inversion.enabled else normalized
    estimate = estimate_mask_gain(inverted, settings.mask.samples.film_base)
    settings.mask.auto = estimate
    balanced = apply_channel_gain(inverted, estimate.rgb_gain)
    styled = apply_output_style(
        balanced,
        style=settings.tone.style,
        exposure=settings.tone.exposure,
        contrast=settings.tone.contrast,
    )
    if max_size is not None:
        styled = resize_float_image(styled, max_size=max_size)
    rendered = np.clip(styled * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return rendered, {"mask_confidence": estimate.confidence}


def resize_float_image(image: np.ndarray, max_size: int) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_size:
        return image
    scale = max_size / float(longest)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    pil = Image.fromarray(np.clip(image * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB")
    resized = pil.resize(size, Image.Resampling.LANCZOS)
    return np.asarray(resized).astype(np.float32) / 255.0


def _neutralizing_gain(rgb: np.ndarray) -> np.ndarray:
    safe = np.clip(rgb.astype(np.float32), 1e-6, None)
    target = float(np.mean(safe))
    gain = target / safe
    return gain / float(np.median(gain))
```

- [ ] **Step 4: Run pipeline tests**

Run:

```powershell
uv run pytest tests/core/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_core/pipeline.py tests/core/test_pipeline.py
git commit -m "feat: add color negative inversion pipeline"
```

---

### Task 4: Image Input and Preview Rendering

**Files:**
- Create: `src/filmcolor_core/raw.py`
- Create: `src/filmcolor_core/render.py`
- Modify: `tests/core/test_pipeline.py`

- [ ] **Step 1: Add rendering tests**

Append to `tests/core/test_pipeline.py`:

```python
from pathlib import Path

from PIL import Image

from filmcolor_core.raw import decode_to_linear_rgb
from filmcolor_core.render import render_preview_file


def test_decode_to_linear_rgb_reads_common_image_fixture(tmp_path: Path):
    source = tmp_path / "capture.png"
    Image.new("RGB", (4, 2), color=(64, 128, 192)).save(source)

    decoded = decode_to_linear_rgb(source)

    assert decoded.data.shape == (2, 4, 3)
    assert decoded.data.dtype == np.float32
    assert decoded.metadata["decoder"] == "pillow"


def test_render_preview_file_writes_webp(tmp_path: Path):
    source = tmp_path / "capture.png"
    output = tmp_path / "preview.webp"
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source)

    diagnostics = render_preview_file(source, output, PipelineSettings(), max_size=4)

    assert output.exists()
    assert diagnostics["mask_confidence"] == 0.55
    assert Image.open(output).size == (4, 4)
```

- [ ] **Step 2: Run rendering tests to verify they fail**

Run:

```powershell
uv run pytest tests/core/test_pipeline.py::test_decode_to_linear_rgb_reads_common_image_fixture tests/core/test_pipeline.py::test_render_preview_file_writes_webp -v
```

Expected: FAIL with import errors for `filmcolor_core.raw`.

- [ ] **Step 3: Implement image decoding adapter**

Create `src/filmcolor_core/raw.py`:

```python
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
        raise RuntimeError(
            "RAW decoding requires the optional raw extra: uv sync --extra raw"
        ) from exc

    with rawpy.imread(str(path)) as raw:
        rgb16 = raw.postprocess(
            output_bps=16,
            no_auto_bright=True,
            use_camera_wb=True,
            gamma=(1, 1),
        )
    linear = rgb16.astype(np.float32) / 65535.0
    return DecodedImage(data=np.clip(linear, 0.0, 1.0), metadata={"decoder": "rawpy", "path": path.as_posix()})
```

- [ ] **Step 4: Implement preview rendering**

Create `src/filmcolor_core/render.py`:

```python
from __future__ import annotations

from pathlib import Path

from PIL import Image

from filmcolor_core.models import PipelineSettings
from filmcolor_core.pipeline import render_pipeline_array
from filmcolor_core.raw import decode_to_linear_rgb


def render_preview_file(
    source_path: Path,
    output_path: Path,
    settings: PipelineSettings,
    max_size: int = 1600,
) -> dict[str, float]:
    decoded = decode_to_linear_rgb(source_path)
    rendered, diagnostics = render_pipeline_array(decoded.data, settings, max_size=max_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rendered, mode="RGB").save(output_path, quality=90)
    return diagnostics
```

- [ ] **Step 5: Run core tests**

Run:

```powershell
uv run pytest tests/core -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/filmcolor_core/raw.py src/filmcolor_core/render.py tests/core/test_pipeline.py
git commit -m "feat: add image decoding and preview rendering"
```

---

### Task 5: Workspace Storage and Roll Import

**Files:**
- Create: `src/filmcolor_server/storage.py`
- Create: `tests/server/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Create `tests/server/test_storage.py`:

```python
from pathlib import Path

from PIL import Image

from filmcolor_core.models import FrameStatus
from filmcolor_server.storage import Workspace


def test_import_roll_creates_roll_and_frame_sidecars(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source / "IMG_0001.png")
    Image.new("RGB", (4, 4), color=(40, 50, 60)).save(source / "IMG_0002.jpg")

    workspace = Workspace(tmp_path / "workspace")
    roll = workspace.import_roll(source, name="E100 Test")
    frames = workspace.list_frames(roll.id)

    assert roll.name == "E100 Test"
    assert len(frames) == 2
    assert frames[0].status == FrameStatus.UNPROCESSED
    assert (tmp_path / "workspace" / "rolls" / roll.id / "roll.json").exists()


def test_update_frame_pipeline_marks_manual_adjustment(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source / "IMG_0001.png")

    workspace = Workspace(tmp_path / "workspace")
    roll = workspace.import_roll(source, name="E100 Test")
    frame = workspace.list_frames(roll.id)[0]

    updated = workspace.update_frame_pipeline(
        roll.id,
        frame.frame_id,
        {"tone": {"style": "share", "exposure": 0.5}},
    )

    assert updated.status == FrameStatus.MANUALLY_ADJUSTED
    assert updated.pipeline.tone.style == "share"
    assert updated.pipeline.tone.exposure == 0.5
```

- [ ] **Step 2: Run storage tests to verify they fail**

Run:

```powershell
uv run pytest tests/server/test_storage.py -v
```

Expected: FAIL with import errors for `filmcolor_server.storage`.

- [ ] **Step 3: Implement workspace storage**

Create `src/filmcolor_server/storage.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from filmcolor_core.models import FrameSidecar, FrameStatus, PipelineSettings, RollMetadata
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
        rolls = []
        for path in sorted(self.rolls_dir.glob("*/roll.json")):
            rolls.append(read_roll_metadata(path))
        return rolls

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
```

- [ ] **Step 4: Run storage tests**

Run:

```powershell
uv run pytest tests/server/test_storage.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_server/storage.py tests/server/test_storage.py
git commit -m "feat: add workspace storage"
```

---

### Task 6: FastAPI App and Job Registry

**Files:**
- Create: `src/filmcolor_server/jobs.py`
- Create: `src/filmcolor_server/app.py`
- Create: `tests/server/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/server/test_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from filmcolor_server.app import create_app


def test_import_roll_and_list_frames(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    client = TestClient(create_app(workspace_root=tmp_path / "workspace"))

    response = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "E100"})

    assert response.status_code == 200
    roll = response.json()
    frames = client.get(f"/api/rolls/{roll['id']}/frames").json()
    assert len(frames) == 1
    assert frames[0]["frame_id"] == "IMG_0001"


def test_patch_pipeline_and_render_preview(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    client = TestClient(create_app(workspace_root=tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "E100"}).json()

    patch = client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"tone": {"style": "share", "exposure": 0.25}},
    )
    assert patch.status_code == 200
    assert patch.json()["pipeline"]["tone"]["style"] == "share"

    preview = client.post(f"/api/rolls/{roll['id']}/frames/IMG_0001/render-preview")
    assert preview.status_code == 200
    assert preview.json()["status"] == "succeeded"
    assert preview.json()["diagnostics"]["mask_confidence"] == 0.55
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```powershell
uv run pytest tests/server/test_api.py -v
```

Expected: FAIL with import errors for `filmcolor_server.app`.

- [ ] **Step 3: Implement job registry**

Create `src/filmcolor_server/jobs.py`:

```python
from __future__ import annotations

from itertools import count

from filmcolor_core.models import JobRecord, JobStatus


class JobRegistry:
    def __init__(self) -> None:
        self._counter = count(1)
        self._jobs: dict[str, JobRecord] = {}

    def create(self, kind: str, message: str = "") -> JobRecord:
        job_id = f"job-{next(self._counter):06d}"
        job = JobRecord(id=job_id, kind=kind, status=JobStatus.QUEUED, message=message)
        self._jobs[job_id] = job
        return job

    def set_running(self, job_id: str, message: str = "") -> JobRecord:
        job = self._jobs[job_id]
        job.status = JobStatus.RUNNING
        job.message = message
        return job

    def set_succeeded(self, job_id: str, message: str = "", progress: float = 1.0) -> JobRecord:
        job = self._jobs[job_id]
        job.status = JobStatus.SUCCEEDED
        job.message = message
        job.progress = progress
        return job

    def set_failed(self, job_id: str, message: str) -> JobRecord:
        job = self._jobs[job_id]
        job.status = JobStatus.FAILED
        job.message = message
        return job

    def get(self, job_id: str) -> JobRecord:
        return self._jobs[job_id]
```

- [ ] **Step 4: Implement FastAPI app**

Create `src/filmcolor_server/app.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from filmcolor_core.render import render_preview_file
from filmcolor_core.sidecar import write_frame_sidecar
from filmcolor_server.jobs import JobRegistry
from filmcolor_server.storage import Workspace


class ImportRollRequest(BaseModel):
    source_dir: str
    name: str


class PipelinePatchRequest(BaseModel):
    tone: dict[str, Any] | None = None
    mask: dict[str, Any] | None = None
    inversion: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None

    def patch_data(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def create_app(workspace_root: Path | None = None) -> FastAPI:
    app = FastAPI(title="Filmcolor")
    workspace = Workspace(workspace_root or Path.cwd() / ".filmcolor-workspace")
    jobs = JobRegistry()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/rolls/import")
    def import_roll(request: ImportRollRequest):
        try:
            return workspace.import_roll(Path(request.source_dir), request.name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/rolls")
    def list_rolls():
        return workspace.list_rolls()

    @app.get("/api/rolls/{roll_id}")
    def get_roll(roll_id: str):
        return workspace.get_roll(roll_id)

    @app.get("/api/rolls/{roll_id}/frames")
    def list_frames(roll_id: str):
        return workspace.list_frames(roll_id)

    @app.get("/api/rolls/{roll_id}/frames/{frame_id}")
    def get_frame(roll_id: str, frame_id: str):
        return workspace.get_frame(roll_id, frame_id)

    @app.patch("/api/rolls/{roll_id}/frames/{frame_id}/pipeline")
    def patch_pipeline(roll_id: str, frame_id: str, request: PipelinePatchRequest):
        return workspace.update_frame_pipeline(roll_id, frame_id, request.patch_data())

    @app.post("/api/rolls/{roll_id}/frames/{frame_id}/render-preview")
    def render_preview(roll_id: str, frame_id: str):
        job = jobs.create("render-preview", message=f"Rendering {frame_id}")
        jobs.set_running(job.id, message=f"Rendering {frame_id}")
        try:
            frame = workspace.get_frame(roll_id, frame_id)
            output_path = workspace.preview_path(roll_id, frame_id)
            diagnostics = render_preview_file(Path(frame.source.path), output_path, frame.pipeline, max_size=1600)
            frame.pipeline.mask.auto.confidence = diagnostics["mask_confidence"]
            write_frame_sidecar(
                workspace.root / "rolls" / roll_id / "frames" / f"{frame_id}.xmp.json",
                frame,
            )
            jobs.set_succeeded(job.id, message=f"Rendered {frame_id}")
            return {"job_id": job.id, "status": "succeeded", "preview_url": f"/api/rolls/{roll_id}/frames/{frame_id}/preview", "diagnostics": diagnostics}
        except Exception as exc:
            jobs.set_failed(job.id, str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/rolls/{roll_id}/frames/{frame_id}/preview")
    def get_preview(roll_id: str, frame_id: str):
        path = workspace.preview_path(roll_id, frame_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Preview has not been rendered")
        return FileResponse(path)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        try:
            return jobs.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}") from exc

    return app


app = create_app()
```

- [ ] **Step 5: Run server tests**

Run:

```powershell
uv run pytest tests/server -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/filmcolor_server/jobs.py src/filmcolor_server/app.py tests/server/test_api.py
git commit -m "feat: add local api for rolls and previews"
```

---

### Task 7: Web Project Scaffold

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.node.json`
- Create: `web/vite.config.ts`
- Create: `web/src/main.tsx`
- Create: `web/src/types.ts`
- Create: `web/src/api.ts`

- [ ] **Step 1: Create frontend package files**

Create `web/package.json`:

```json
{
  "name": "filmcolor-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc && vite build",
    "test": "vitest run",
    "preview": "vite preview --host 127.0.0.1"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "typescript": "^5.5.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "jsdom": "^25.0.0",
    "vitest": "^2.1.0"
  }
}
```

Create `web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Filmcolor</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `web/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

Create `web/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["@testing-library/jest-dom/vitest"]
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000"
    }
  }
});
```

Create `web/src/types.ts`:

```typescript
export type OutputStyle = "faithful" | "neutral" | "share";

export interface RollMetadata {
  id: string;
  name: string;
  source_dir: string;
  created_at: string;
  defaults: {
    film_profile: string;
    output_style: OutputStyle;
    color_space: string;
  };
}

export interface FrameSidecar {
  frame_id: string;
  status: string;
  source: {
    path: string;
    sha256: string;
    camera: string | null;
    lens: string | null;
    captured_at: string | null;
  };
  pipeline: {
    tone: {
      style: OutputStyle;
      exposure: number;
      contrast: number;
      black_point: number;
      white_point: number;
    };
    mask: {
      auto: {
        rgb_gain: number[];
        confidence: number;
      };
      samples: {
        film_base: number[][];
        gray: number[][];
        white: number[][];
      };
    };
  };
  exports: unknown[];
  error: string | null;
}
```

Create `web/src/api.ts`:

```typescript
import type { FrameSidecar, OutputStyle, RollMetadata } from "./types";

export async function listRolls(): Promise<RollMetadata[]> {
  const response = await fetch("/api/rolls");
  return readJson(response);
}

export async function listFrames(rollId: string): Promise<FrameSidecar[]> {
  const response = await fetch(`/api/rolls/${rollId}/frames`);
  return readJson(response);
}

export async function setFrameStyle(
  rollId: string,
  frameId: string,
  style: OutputStyle
): Promise<FrameSidecar> {
  const response = await fetch(`/api/rolls/${rollId}/frames/${frameId}/pipeline`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tone: { style } })
  });
  return readJson(response);
}

export async function renderPreview(rollId: string, frameId: string): Promise<{ preview_url: string }> {
  const response = await fetch(`/api/rolls/${rollId}/frames/${frameId}/render-preview`, {
    method: "POST"
  });
  return readJson(response);
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}
```

Create `web/src/main.tsx`:

```typescript
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 2: Install frontend dependencies**

Run:

```powershell
Set-Location web
npm install
Set-Location ..
```

Expected: `node_modules` and `package-lock.json` are created.

- [ ] **Step 3: Commit**

```powershell
git add web/package.json web/package-lock.json web/index.html web/tsconfig.json web/tsconfig.node.json web/vite.config.ts web/src/main.tsx web/src/types.ts web/src/api.ts
git commit -m "chore: scaffold web app"
```

---

### Task 8: Web Workbench MVP

**Files:**
- Create: `web/src/App.tsx`
- Create: `web/src/styles.css`
- Create: `web/src/App.test.tsx`

- [ ] **Step 1: Write failing frontend test**

Create `web/src/App.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the filmcolor workbench shell", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => []
      }))
    );

    render(<App />);

    expect(await screen.findByText("Filmcolor")).toBeInTheDocument();
    expect(screen.getByText("ROLL")).toBeInTheDocument();
    expect(screen.getByText("FRAME")).toBeInTheDocument();
    expect(screen.getByText("faithful")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run frontend test to verify it fails**

Run:

```powershell
Set-Location web
npm test -- src/App.test.tsx
Set-Location ..
```

Expected: FAIL because `App.tsx` does not exist.

- [ ] **Step 3: Implement workbench component**

Create `web/src/App.tsx`:

```typescript
import { Aperture, Grid2X2, ImageIcon, Play, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { listFrames, listRolls, renderPreview, setFrameStyle } from "./api";
import type { FrameSidecar, OutputStyle, RollMetadata } from "./types";

const styles: OutputStyle[] = ["faithful", "neutral", "share"];

export function App() {
  const [rolls, setRolls] = useState<RollMetadata[]>([]);
  const [selectedRollId, setSelectedRollId] = useState<string>("");
  const [frames, setFrames] = useState<FrameSidecar[]>([]);
  const [selectedFrameId, setSelectedFrameId] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    listRolls()
      .then((items) => {
        setRolls(items);
        setSelectedRollId(items[0]?.id ?? "");
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedRollId) {
      setFrames([]);
      return;
    }
    listFrames(selectedRollId)
      .then((items) => {
        setFrames(items);
        setSelectedFrameId(items[0]?.frame_id ?? "");
      })
      .catch((err: Error) => setError(err.message));
  }, [selectedRollId]);

  const selectedFrame = useMemo(
    () => frames.find((frame) => frame.frame_id === selectedFrameId) ?? null,
    [frames, selectedFrameId]
  );

  async function chooseStyle(style: OutputStyle) {
    if (!selectedRollId || !selectedFrame) return;
    const updated = await setFrameStyle(selectedRollId, selectedFrame.frame_id, style);
    setFrames((current) =>
      current.map((frame) => (frame.frame_id === updated.frame_id ? updated : frame))
    );
  }

  async function handleRenderPreview() {
    if (!selectedRollId || !selectedFrame) return;
    const result = await renderPreview(selectedRollId, selectedFrame.frame_id);
    setPreviewUrl(`${result.preview_url}?t=${Date.now()}`);
  }

  return (
    <main className="shell">
      <aside className="rolls" aria-label="Roll list">
        <div className="brand">
          <Aperture aria-hidden="true" size={22} />
          <h1>Filmcolor</h1>
        </div>
        <div className="sectionLabel">ROLL</div>
        {rolls.length === 0 ? (
          <div className="empty">No rolls imported</div>
        ) : (
          rolls.map((roll) => (
            <button
              className={roll.id === selectedRollId ? "roll active" : "roll"}
              key={roll.id}
              onClick={() => setSelectedRollId(roll.id)}
            >
              <span>{roll.name}</span>
              <small>{roll.id}</small>
            </button>
          ))
        )}
      </aside>

      <section className="table">
        <header className="toolbar">
          <div>
            <div className="sectionLabel">FRAME</div>
            <strong>{selectedFrame?.frame_id ?? "No frame selected"}</strong>
          </div>
          <button className="iconButton" onClick={handleRenderPreview} aria-label="Render preview">
            <Play size={18} />
          </button>
        </header>

        <div className="preview">
          {previewUrl ? (
            <img src={previewUrl} alt="Rendered film preview" />
          ) : (
            <div className="previewEmpty">
              <ImageIcon size={34} />
              <span>Render a preview</span>
            </div>
          )}
        </div>

        <div className="gridHeader">
          <Grid2X2 size={16} />
          <span>Contact Sheet</span>
        </div>
        <div className="frames">
          {frames.map((frame) => (
            <button
              key={frame.frame_id}
              className={frame.frame_id === selectedFrameId ? "frame active" : "frame"}
              onClick={() => {
                setSelectedFrameId(frame.frame_id);
                setPreviewUrl("");
              }}
            >
              <span>{frame.frame_id}</span>
              <small>{frame.status}</small>
            </button>
          ))}
        </div>
      </section>

      <aside className="panel">
        <div className="panelTitle">
          <SlidersHorizontal size={18} />
          <span>Pipeline</span>
        </div>
        <div className="sectionLabel">STYLE</div>
        <div className="segmented">
          {styles.map((style) => (
            <button
              key={style}
              className={selectedFrame?.pipeline.tone.style === style ? "selected" : ""}
              onClick={() => chooseStyle(style)}
            >
              {style}
            </button>
          ))}
        </div>
        <dl className="readout">
          <div>
            <dt>Mask confidence</dt>
            <dd>{selectedFrame?.pipeline.mask.auto.confidence.toFixed(2) ?? "0.00"}</dd>
          </div>
          <div>
            <dt>Exposure</dt>
            <dd>{selectedFrame?.pipeline.tone.exposure.toFixed(2) ?? "0.00"}</dd>
          </div>
          <div>
            <dt>Contrast</dt>
            <dd>{selectedFrame?.pipeline.tone.contrast.toFixed(2) ?? "0.00"}</dd>
          </div>
        </dl>
        {error ? <p className="error">{error}</p> : null}
      </aside>
    </main>
  );
}
```

- [ ] **Step 4: Implement Modern Darkroom styling**

Create `web/src/styles.css`:

```css
:root {
  color: #171717;
  background: #f6f3ec;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button {
  font: inherit;
}

.shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 300px;
  min-height: 100vh;
  background: #f6f3ec;
}

.rolls,
.panel {
  padding: 24px;
  border-color: #ded8cc;
  background: #fbfaf6;
}

.rolls {
  border-right: 1px solid #ded8cc;
}

.panel {
  border-left: 1px solid #ded8cc;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 34px;
}

.brand h1 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0;
}

.sectionLabel {
  margin-bottom: 10px;
  color: #9a3412;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 11px;
  font-weight: 700;
}

.empty,
.previewEmpty {
  color: #706a60;
}

.roll,
.frame,
.iconButton,
.segmented button {
  border: 1px solid #d8d1c4;
  background: #fffdf8;
  color: #171717;
  cursor: pointer;
}

.roll {
  display: grid;
  width: 100%;
  gap: 5px;
  margin-bottom: 8px;
  padding: 12px;
  text-align: left;
  border-radius: 8px;
}

.roll small,
.frame small {
  color: #706a60;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 11px;
}

.roll.active,
.frame.active,
.segmented .selected {
  border-color: #c26b2b;
  box-shadow: inset 0 0 0 1px #c26b2b;
}

.table {
  display: grid;
  grid-template-rows: auto minmax(280px, 1fr) auto 190px;
  min-width: 0;
  padding: 24px;
  gap: 18px;
}

.toolbar,
.panelTitle,
.gridHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.iconButton {
  display: inline-grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 8px;
}

.preview {
  display: grid;
  min-height: 320px;
  place-items: center;
  overflow: hidden;
  border: 1px solid #ded8cc;
  background: #fffefa;
}

.preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.previewEmpty {
  display: grid;
  place-items: center;
  gap: 12px;
}

.gridHeader {
  justify-content: flex-start;
  color: #4d4840;
  font-weight: 700;
}

.frames {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 10px;
  overflow: auto;
  padding-bottom: 4px;
}

.frame {
  display: grid;
  align-content: space-between;
  min-height: 82px;
  padding: 10px;
  border-radius: 6px;
  text-align: left;
  background:
    linear-gradient(90deg, transparent 0 8px, rgba(194, 107, 43, 0.18) 8px 10px, transparent 10px),
    #fffdf8;
}

.panelTitle {
  justify-content: flex-start;
  margin-bottom: 24px;
  font-weight: 800;
}

.segmented {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin-bottom: 24px;
}

.segmented button {
  min-width: 0;
  padding: 9px 6px;
  border-radius: 7px;
  font-size: 13px;
}

.readout {
  display: grid;
  gap: 12px;
  margin: 0;
}

.readout div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e3ded3;
}

.readout dt {
  color: #706a60;
}

.readout dd {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.error {
  margin-top: 20px;
  color: #a12424;
}

@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .rolls,
  .panel {
    border: 0;
    border-bottom: 1px solid #ded8cc;
  }
}
```

- [ ] **Step 5: Run frontend tests and build**

Run:

```powershell
Set-Location web
npm test -- src/App.test.tsx
npm run build
Set-Location ..
```

Expected: test PASS and build succeeds.

- [ ] **Step 6: Commit**

```powershell
git add web/src/App.tsx web/src/styles.css web/src/App.test.tsx
git commit -m "feat: add web workbench mvp"
```

---

### Task 9: End-to-End Developer Workflow

**Files:**
- Modify: `README.md`
- Create: `tests/server/test_api.py` updates only if previous tasks reveal integration naming mismatches

- [ ] **Step 1: Update README with run commands**

Replace `README.md` with:

```markdown
# Filmcolor

Filmcolor is a local color negative processing workbench. It keeps original captures unchanged, stores processing decisions in JSON sidecars, and renders previews or exports from reproducible pipeline parameters.

## Development Setup

Install Python dependencies:

```powershell
uv sync --extra dev
```

Install frontend dependencies:

```powershell
Set-Location web
npm install
Set-Location ..
```

## Run Tests

Python:

```powershell
uv run pytest
```

Frontend:

```powershell
Set-Location web
npm test
npm run build
Set-Location ..
```

## Run Locally

Start the API:

```powershell
uv run uvicorn filmcolor_server.app:app --reload --host 127.0.0.1 --port 8000
```

Start the web app:

```powershell
Set-Location web
npm run dev
Set-Location ..
```

Open the Vite URL shown in the terminal. The frontend proxies `/api` requests to `http://127.0.0.1:8000`.

## MVP Workflow

1. Put sample PNG/JPEG/TIFF or supported RAW files in a local folder.
2. Use `POST /api/rolls/import` with the folder path and a roll name.
3. Open the web app to browse imported rolls and frames.
4. Render a preview for a selected frame.
5. Switch output style between `faithful`, `neutral`, and `share`.
```

- [ ] **Step 2: Run full verification**

Run:

```powershell
uv run pytest
Set-Location web
npm test
npm run build
Set-Location ..
```

Expected: all Python tests pass, all frontend tests pass, and Vite build succeeds.

- [ ] **Step 3: Commit**

```powershell
git add README.md
git commit -m "docs: add mvp developer workflow"
```

---

### Task 10: Manual Smoke Run

**Files:**
- No planned file changes

- [ ] **Step 1: Start the API server**

Run:

```powershell
uv run uvicorn filmcolor_server.app:app --reload --host 127.0.0.1 --port 8000
```

Expected: server logs include `Uvicorn running on http://127.0.0.1:8000`.

- [ ] **Step 2: Start the web dev server in a second terminal**

Run:

```powershell
Set-Location web
npm run dev
```

Expected: Vite prints a local URL such as `http://127.0.0.1:5173/`.

- [ ] **Step 3: Create and import a sample roll through the API**

Run:

```powershell
New-Item -ItemType Directory -Force -Path D:/filmcolor/sample-roll | Out-Null
@'
from pathlib import Path
from PIL import Image

root = Path("D:/filmcolor/sample-roll")
Image.new("RGB", (256, 180), color=(64, 128, 192)).save(root / "IMG_0001.png")
Image.new("RGB", (256, 180), color=(120, 90, 60)).save(root / "IMG_0002.png")
'@ | python -
```

Expected: `D:/filmcolor/sample-roll/IMG_0001.png` and `D:/filmcolor/sample-roll/IMG_0002.png` exist.

Run:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/rolls/import -ContentType "application/json" -Body '{"source_dir":"D:/filmcolor/sample-roll","name":"Sample Roll"}'
```

Expected: JSON response includes `id`, `name`, `source_dir`, `created_at`, and `defaults`.

- [ ] **Step 4: Verify the browser workflow**

In the Vite URL:

- Confirm the roll appears in the left sidebar.
- Confirm frames appear in the contact sheet.
- Select one frame.
- Click the render preview button.
- Switch between `faithful`, `neutral`, and `share`.

Expected: no console errors, selected style updates, and the preview appears after rendering.

- [ ] **Step 5: Commit only if smoke-run fixes were needed**

If code changes were required during smoke testing, commit the focused fix:

```powershell
git status --short
git add -A
git commit -m "fix: complete mvp smoke workflow"
```

If no changes were required, do not create an empty commit.

---

## Plan Self-Review

Spec coverage:

- Algorithm library: covered by Tasks 1, 3, and 4.
- Sidecar and reproducibility: covered by Tasks 2 and 5.
- FastAPI backend and local jobs: covered by Tasks 5 and 6.
- Web workbench: covered by Tasks 7 and 8.
- Three output styles: covered by Tasks 3 and 8.
- Whole-roll organization: covered by Tasks 5, 6, and 8.
- Tests: covered in each implementation task plus full verification in Task 9.
- Modern Darkroom / Light Table visual direction: covered by Task 8 CSS.

Deferred from this MVP and still aligned with the spec:

- Full-resolution TIFF/JPEG export queue is not implemented in this first vertical slice; preview rendering and style persistence come first.
- Interactive film-base/gray/white click sampling is represented in the sidecar model and pipeline, but browser click placement is left for the next plan.
- True RAW decoding is supported through the `rawpy` adapter boundary, but fixture tests use deterministic PNG/JPEG input to keep CI and local setup lightweight.

