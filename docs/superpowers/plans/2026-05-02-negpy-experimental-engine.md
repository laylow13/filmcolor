# NegPy Experimental Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NegPy as an optional experimental preview engine while keeping Filmcolor's default pipeline independent and fully functional without NegPy installed.

**Architecture:** NegPy is added as `vendor/NegPy` git submodule and accessed only through `filmcolor_core.negpy_adapter`. The backend exposes engine availability and dispatches preview rendering by `pipeline.engine`; the frontend adds an engine selector that can enable `NegPy Experimental` when available.

**Tech Stack:** Python 3.13+ managed by uv, pytest, FastAPI, Pydantic, Pillow, optional NegPy submodule, React, TypeScript, Vite, Vitest.

---

## Scope

This plan implements the first narrow vertical slice:

- Submodule entry and docs for `vendor/NegPy`.
- Optional `negpy` dependency group.
- NegPy adapter availability checks.
- Fake-tested in-process adapter success path that does not require real NegPy dependencies in default tests.
- Sidecar model extensions for engine choice and NegPy settings.
- Backend `GET /api/engines`.
- Preview dispatch by engine.
- Frontend engine selector and unavailable-state messaging.

This plan does not implement real full-fidelity NegPy rendering against the actual upstream package in automated tests. The adapter has a real import path and call structure, but default verification uses fakes so CI/local default setup remains lightweight and GPU-free.

## File Structure

Create or modify:

```text
D:/filmcolor/
  .gitmodules
  README.md
  pyproject.toml
  docs/superpowers/plans/2026-05-02-negpy-experimental-engine.md
  vendor/NegPy                       # git submodule
  src/filmcolor_core/
    models.py                        # engine and NegPy sidecar models
    negpy_adapter.py                 # only Filmcolor module importing NegPy internals
    render.py                        # engine dispatch helper
  src/filmcolor_server/
    app.py                           # GET /api/engines and preview dispatch
    storage.py                       # pipeline/engine patch persistence
  tests/core/
    test_negpy_adapter.py
    test_sidecar.py                  # sidecar round-trip coverage
    test_pipeline.py                 # Filmcolor default preview remains green
  tests/server/
    test_api.py                      # engine endpoint and preview dispatch
  web/src/
    App.tsx
    App.test.tsx
    api.ts
    types.ts
```

Key boundaries:

- `filmcolor_core.negpy_adapter` owns all `sys.path` manipulation and all NegPy imports.
- `filmcolor_core.render` owns engine dispatch and keeps `render_preview_file` available for existing callers.
- `filmcolor_server.app` does not import NegPy directly.
- Frontend treats `engine` as algorithm selection, not output style.

---

### Task 1: Add NegPy Submodule and Documentation

**Files:**
- Create: `.gitmodules`
- Create: `vendor/NegPy`
- Modify: `README.md`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the NegPy submodule**

Run:

```powershell
git submodule add https://github.com/marcinz606/NegPy.git vendor/NegPy
```

Expected: `.gitmodules` exists and `vendor/NegPy` is a gitlink.

- [ ] **Step 2: Add optional NegPy dependency extra**

Modify `pyproject.toml` so `[project.optional-dependencies]` includes:

```toml
negpy = [
  "rawpy==0.25.1",
  "tifffile==2026.4.11",
  "imagecodecs==2026.3.6",
  "imageio==2.37.3",
  "jinja2==3.1.6",
  "llvmlite==0.44.0",
  "numba==0.61.2",
  "opencv-python-headless==4.13.0.92",
  "pyqt6==6.11.0",
  "pyqt6-charts==6.11.0",
  "qtawesome==1.4.2",
  "wgpu==0.31.0"
]
```

Do not add NegPy dependencies to the default dependency list.

- [ ] **Step 3: Update README instructions and attribution**

Add this section to `README.md` after "Development Setup":

```markdown
## Optional NegPy Experimental Engine

Filmcolor can use [NegPy](https://github.com/marcinz606/NegPy) as an optional experimental preview engine for color negative conversion. NegPy is GPL-3.0; enabling this engine uses GPL-3.0 code from the NegPy project.

Initialize the submodule:

```powershell
git submodule update --init --recursive
```

Install the optional dependencies:

```powershell
uv sync --extra dev --extra negpy
```

The default Filmcolor engine does not require NegPy. If the submodule or optional dependencies are missing, `NegPy Experimental` is shown as unavailable and the Filmcolor engine continues to work.
```

- [ ] **Step 4: Verify default dependency sync still works**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv sync --extra dev
```

Expected: sync succeeds without installing the `negpy` extra.

- [ ] **Step 5: Commit**

```powershell
git add .gitmodules vendor/NegPy README.md pyproject.toml
git commit -m "chore: add NegPy experimental submodule"
```

---

### Task 2: Sidecar Engine Models

**Files:**
- Modify: `src/filmcolor_core/models.py`
- Modify: `tests/core/test_sidecar.py`

- [ ] **Step 1: Write failing sidecar tests**

Append to `tests/core/test_sidecar.py`:

```python
from filmcolor_core.models import ProcessingEngine


def test_frame_sidecar_defaults_to_filmcolor_engine(workspace_tmp_path: Path):
    sidecar = FrameSidecar.create(
        frame_id="IMG_0003",
        source_path=Path("D:/film/raw/E100-test/IMG_0003.CR3"),
        sha256="def456",
    )

    path = workspace_tmp_path / "IMG_0003.xmp.json"
    write_frame_sidecar(path, sidecar)
    loaded = read_frame_sidecar(path)

    assert loaded.pipeline.engine == ProcessingEngine.FILMCOLOR
    assert loaded.engines.negpy.enabled is False
    assert loaded.engines.negpy.backend == "cpu"
    assert loaded.engines.negpy.params.mode == "C41"


def test_frame_sidecar_round_trips_negpy_engine_settings(workspace_tmp_path: Path):
    sidecar = FrameSidecar.create(
        frame_id="IMG_0004",
        source_path=Path("D:/film/raw/E100-test/IMG_0004.CR3"),
        sha256="ghi789",
    )
    sidecar.pipeline.engine = ProcessingEngine.NEGPY
    sidecar.engines.negpy.enabled = True
    sidecar.engines.negpy.source_commit = "abc123"
    sidecar.engines.negpy.params.preset = "default"
    sidecar.engines.negpy.diagnostics = {"adapter": "in_process", "backend": "cpu"}

    path = workspace_tmp_path / "IMG_0004.xmp.json"
    write_frame_sidecar(path, sidecar)
    loaded = read_frame_sidecar(path)

    assert loaded.pipeline.engine == ProcessingEngine.NEGPY
    assert loaded.engines.negpy.enabled is True
    assert loaded.engines.negpy.source_commit == "abc123"
    assert loaded.engines.negpy.params.preset == "default"
    assert loaded.engines.negpy.diagnostics["adapter"] == "in_process"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/core/test_sidecar.py -v
```

Expected: FAIL with import error for `ProcessingEngine` or missing `pipeline.engine`.

- [ ] **Step 3: Implement engine models**

Modify `src/filmcolor_core/models.py`.

Add after `OutputStyle`:

```python
class ProcessingEngine(StrEnum):
    FILMCOLOR = "filmcolor"
    NEGPY = "negpy"
```

Add before `PipelineSettings`:

```python
class NegPyParams(BaseModel):
    mode: str = "C41"
    preset: str = "default"
    density: float | None = None
    grade: float | None = None
    wb_cyan: float | None = None
    wb_magenta: float | None = None
    wb_yellow: float | None = None


class NegPyEngineSettings(BaseModel):
    enabled: bool = False
    version: str | None = None
    source_commit: str | None = None
    backend: str = "cpu"
    params: NegPyParams = Field(default_factory=NegPyParams)
    diagnostics: dict[str, object] = Field(default_factory=dict)


class EngineSettings(BaseModel):
    negpy: NegPyEngineSettings = Field(default_factory=NegPyEngineSettings)
```

Modify `PipelineSettings` to include:

```python
engine: ProcessingEngine = ProcessingEngine.FILMCOLOR
```

Modify `FrameSidecar` to include:

```python
engines: EngineSettings = Field(default_factory=EngineSettings)
```

- [ ] **Step 4: Run sidecar tests**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/core/test_sidecar.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_core/models.py tests/core/test_sidecar.py
git commit -m "feat: add processing engine sidecar settings"
```

---

### Task 3: NegPy Adapter Availability and Fake Success Path

**Files:**
- Create: `src/filmcolor_core/negpy_adapter.py`
- Create: `tests/core/test_negpy_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/core/test_negpy_adapter.py`:

```python
from pathlib import Path

import numpy as np
from PIL import Image

from filmcolor_core.models import PipelineSettings
from filmcolor_core.negpy_adapter import get_negpy_status, render_negpy_preview


def test_get_negpy_status_reports_missing_submodule(monkeypatch):
    monkeypatch.setattr("filmcolor_core.negpy_adapter._negpy_root", lambda: Path("Z:/missing/NegPy"))

    status = get_negpy_status()

    assert status["available"] is False
    assert status["experimental"] is True
    assert status["backend"] == "cpu"
    assert "submodule" in status["reason"].lower()


def test_render_negpy_preview_uses_injected_runner(workspace_tmp_path: Path, monkeypatch):
    source = workspace_tmp_path / "source.png"
    output = workspace_tmp_path / "preview.webp"
    Image.new("RGB", (6, 4), color=(64, 128, 192)).save(source)

    def fake_runner(source_path: Path, max_size: int):
        assert source_path == source
        assert max_size == 3
        return np.ones((3, 3, 3), dtype=np.float32) * 0.5, {"fake": True}

    monkeypatch.setattr("filmcolor_core.negpy_adapter._run_negpy_cpu", fake_runner)
    monkeypatch.setattr("filmcolor_core.negpy_adapter._negpy_commit", lambda: "abc123")

    diagnostics = render_negpy_preview(source, output, PipelineSettings(), max_size=3)

    assert output.exists()
    assert Image.open(output).size == (3, 3)
    assert diagnostics["adapter"] == "in_process"
    assert diagnostics["backend"] == "cpu"
    assert diagnostics["source_commit"] == "abc123"
    assert diagnostics["fake"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/core/test_negpy_adapter.py -v
```

Expected: FAIL with import error for `filmcolor_core.negpy_adapter`.

- [ ] **Step 3: Implement adapter skeleton**

Create `src/filmcolor_core/negpy_adapter.py`:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from filmcolor_core.models import PipelineSettings


class NegPyUnavailable(RuntimeError):
    pass


def get_negpy_status() -> dict[str, Any]:
    root = _negpy_root()
    if not root.exists():
        return {
            "available": False,
            "experimental": True,
            "backend": "cpu",
            "reason": "NegPy submodule is missing. Run git submodule update --init --recursive.",
        }
    try:
        _import_negpy_modules(root)
    except Exception as exc:
        return {
            "available": False,
            "experimental": True,
            "backend": "cpu",
            "reason": f"NegPy dependencies are not installed or failed to import: {exc}",
        }
    return {
        "available": True,
        "experimental": True,
        "backend": "cpu",
        "commit": _negpy_commit(),
    }


def render_negpy_preview(
    source_path: Path,
    output_path: Path,
    settings: PipelineSettings,
    max_size: int = 1600,
) -> dict[str, Any]:
    del settings
    buffer, metrics = _run_negpy_cpu(source_path, max_size=max_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = np.clip(buffer * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(rendered).save(output_path, quality=90)
    diagnostics: dict[str, Any] = {
        "adapter": "in_process",
        "backend": "cpu",
        "source_commit": _negpy_commit(),
    }
    diagnostics.update(metrics)
    return diagnostics


def _run_negpy_cpu(source_path: Path, max_size: int) -> tuple[np.ndarray, dict[str, Any]]:
    root = _negpy_root()
    if not root.exists():
        raise NegPyUnavailable("NegPy submodule is missing. Run git submodule update --init --recursive.")
    modules = _import_negpy_modules(root)
    darkroom_engine_cls = modules["DarkroomEngine"]
    loader_factory = modules["loader_factory"]
    ensure_rgb = modules["ensure_rgb"]
    uint16_to_float32 = modules["uint16_to_float32"]
    workspace_config_cls = modules["WorkspaceConfig"]

    settings = workspace_config_cls()
    ctx_mgr, metadata = loader_factory.get_loader(str(source_path))
    with ctx_mgr as raw:
        rgb = raw.postprocess(
            gamma=(1, 1),
            no_auto_bright=True,
            use_camera_wb=False,
            user_wb=[1, 1, 1, 1],
            output_bps=16,
        )
    rgb = ensure_rgb(rgb)
    f32_buffer = uint16_to_float32(rgb)
    preview_buffer = _resize_for_preview(f32_buffer, max_size=max_size)
    engine = darkroom_engine_cls()
    metrics: dict[str, Any] = {}
    processed = engine.process(preview_buffer, settings, source_hash=str(source_path))
    if hasattr(engine, "cache"):
        engine.cache.clear()
    metrics["source_loader"] = metadata.get("loader", "negpy")
    return np.asarray(processed, dtype=np.float32), metrics


def _import_negpy_modules(root: Path) -> dict[str, Any]:
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    from negpy.domain.models import WorkspaceConfig
    from negpy.infrastructure.loaders.factory import loader_factory
    from negpy.kernel.image.logic import ensure_rgb, uint16_to_float32
    from negpy.services.rendering.engine import DarkroomEngine

    return {
        "WorkspaceConfig": WorkspaceConfig,
        "DarkroomEngine": DarkroomEngine,
        "loader_factory": loader_factory,
        "ensure_rgb": ensure_rgb,
        "uint16_to_float32": uint16_to_float32,
    }


def _resize_for_preview(image: np.ndarray, max_size: int) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_size:
        return image
    scale = max_size / float(longest)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    pil = Image.fromarray(np.clip(image * 255.0 + 0.5, 0, 255).astype(np.uint8))
    resized = pil.resize(size, Image.Resampling.LANCZOS)
    return np.asarray(resized).astype(np.float32) / 255.0


def _negpy_root() -> Path:
    return Path(__file__).resolve().parents[2] / "vendor" / "NegPy"


def _negpy_commit() -> str | None:
    root = _negpy_root()
    if not root.exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()
```

This CPU path intentionally avoids `ImageProcessor` and `GPUEngine` so the first integration does not initialize WGPU/GPU. Default tests still fake `_run_negpy_cpu`; real NegPy dependency verification is a manual path through `uv sync --extra dev --extra negpy`.

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/core/test_negpy_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_core/negpy_adapter.py tests/core/test_negpy_adapter.py
git commit -m "feat: add NegPy adapter boundary"
```

---

### Task 4: Render Dispatch by Engine

**Files:**
- Modify: `src/filmcolor_core/render.py`
- Modify: `tests/core/test_pipeline.py`

- [ ] **Step 1: Write failing render dispatch tests**

Append to `tests/core/test_pipeline.py`:

```python
def test_render_preview_file_dispatches_to_negpy(workspace_tmp_path: Path, monkeypatch):
    from filmcolor_core.models import ProcessingEngine
    from filmcolor_core.render import render_preview_file

    source = workspace_tmp_path / "capture.png"
    output = workspace_tmp_path / "preview.webp"
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source)

    settings = PipelineSettings()
    settings.engine = ProcessingEngine.NEGPY

    def fake_negpy(source_path, output_path, pipeline_settings, max_size):
        assert source_path == source
        assert output_path == output
        assert pipeline_settings is settings
        assert max_size == 5
        Image.new("RGB", (5, 5), color=(128, 128, 128)).save(output_path)
        return {"adapter": "fake-negpy"}

    monkeypatch.setattr("filmcolor_core.render.render_negpy_preview", fake_negpy)

    diagnostics = render_preview_file(source, output, settings, max_size=5)

    assert diagnostics["adapter"] == "fake-negpy"
    assert Image.open(output).size == (5, 5)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/core/test_pipeline.py::test_render_preview_file_dispatches_to_negpy -v
```

Expected: FAIL because `render_preview_file` does not dispatch to NegPy.

- [ ] **Step 3: Implement render dispatch**

Modify `src/filmcolor_core/render.py`.

Add imports:

```python
from filmcolor_core.models import PipelineSettings, ProcessingEngine
from filmcolor_core.negpy_adapter import render_negpy_preview
```

Change `render_preview_file` to start with:

```python
    if settings.engine == ProcessingEngine.NEGPY:
        return render_negpy_preview(source_path, output_path, settings, max_size=max_size)
```

Then keep the existing Filmcolor rendering path unchanged.

- [ ] **Step 4: Run core tests**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/core -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_core/render.py tests/core/test_pipeline.py
git commit -m "feat: dispatch preview rendering by engine"
```

---

### Task 5: Storage Patch Support for Engine Blocks

**Files:**
- Modify: `src/filmcolor_server/storage.py`
- Modify: `tests/server/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Append to `tests/server/test_storage.py`:

```python
def test_update_frame_pipeline_can_switch_engine(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source / "IMG_0001.png")

    workspace = Workspace(workspace_tmp_path / "workspace")
    roll = workspace.import_roll(source, name="NegPy Test")
    frame = workspace.list_frames(roll.id)[0]

    updated = workspace.update_frame_pipeline(
        roll.id,
        frame.frame_id,
        {"engine": "negpy"},
    )

    assert updated.pipeline.engine == "negpy"
    assert updated.status == FrameStatus.MANUALLY_ADJUSTED


def test_update_frame_engines_can_patch_negpy_settings(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source / "IMG_0001.png")

    workspace = Workspace(workspace_tmp_path / "workspace")
    roll = workspace.import_roll(source, name="NegPy Test")
    frame = workspace.list_frames(roll.id)[0]

    updated = workspace.update_frame_engines(
        roll.id,
        frame.frame_id,
        {"negpy": {"enabled": True, "source_commit": "abc123", "params": {"preset": "default"}}},
    )

    assert updated.engines.negpy.enabled is True
    assert updated.engines.negpy.source_commit == "abc123"
    assert updated.engines.negpy.params.preset == "default"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/server/test_storage.py -v
```

Expected: FAIL because `update_frame_engines` does not exist or engine patch is unsupported.

- [ ] **Step 3: Implement engine patch storage**

Modify `src/filmcolor_server/storage.py`.

Add import:

```python
from filmcolor_core.models import EngineSettings
```

Add method to `Workspace`:

```python
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
```

`update_frame_pipeline` already deep-merges pipeline data. Ensure the new `PipelineSettings.engine` validates `"negpy"` correctly.

- [ ] **Step 4: Run storage tests**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/server/test_storage.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_server/storage.py tests/server/test_storage.py
git commit -m "feat: persist processing engine settings"
```

---

### Task 6: Engine Status API and Preview Failure Diagnostics

**Files:**
- Modify: `src/filmcolor_server/app.py`
- Modify: `tests/server/test_api.py`

- [ ] **Step 1: Write failing API tests**

Append to `tests/server/test_api.py`:

```python
def test_get_engines_reports_negpy_status(workspace_tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "filmcolor_server.app.get_negpy_status",
        lambda: {"available": False, "experimental": True, "backend": "cpu", "reason": "missing"},
    )
    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))

    response = client.get("/api/engines")

    assert response.status_code == 200
    assert response.json()["filmcolor"]["available"] is True
    assert response.json()["negpy"]["available"] is False
    assert response.json()["negpy"]["reason"] == "missing"


def test_patch_endpoint_updates_engine_block(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "NegPy"}).json()

    response = client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"engine": "negpy", "engines": {"negpy": {"enabled": True}}},
    )

    assert response.status_code == 200
    assert response.json()["pipeline"]["engine"] == "negpy"
    assert response.json()["engines"]["negpy"]["enabled"] is True


def test_negpy_preview_failure_persists_diagnostics(workspace_tmp_path: Path, monkeypatch):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    def fail_render(*args, **kwargs):
        raise RuntimeError("negpy exploded")

    monkeypatch.setattr("filmcolor_core.render.render_negpy_preview", fail_render)
    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "NegPy"}).json()
    client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"engine": "negpy", "engines": {"negpy": {"enabled": True}}},
    )

    response = client.post(f"/api/rolls/{roll['id']}/frames/IMG_0001/render-preview")

    assert response.status_code == 500
    frame = client.get(f"/api/rolls/{roll['id']}/frames/IMG_0001").json()
    assert frame["engines"]["negpy"]["diagnostics"]["error"] == "negpy exploded"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/server/test_api.py -v
```

Expected: FAIL because `/api/engines`, `engines` patching, or diagnostics persistence is missing.

- [ ] **Step 3: Implement engine API**

Modify `src/filmcolor_server/app.py`.

Add imports:

```python
from filmcolor_core.negpy_adapter import get_negpy_status
from filmcolor_core.sidecar import write_frame_sidecar
```

Add endpoint inside `create_app`:

```python
    @app.get("/api/engines")
    def get_engines():
        return {
            "filmcolor": {"available": True},
            "negpy": get_negpy_status(),
        }
```

Modify `PipelinePatchRequest`:

```python
class PipelinePatchRequest(BaseModel):
    engine: str | None = None
    tone: dict[str, Any] | None = None
    mask: dict[str, Any] | None = None
    inversion: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    engines: dict[str, Any] | None = None

    def pipeline_patch_data(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        data.pop("engines", None)
        return data
```

Update patch route:

```python
        frame = workspace.update_frame_pipeline(roll_id, frame_id, request.pipeline_patch_data())
        if request.engines:
            frame = workspace.update_frame_engines(roll_id, frame_id, request.engines)
        return frame
```

In render preview exception block, persist NegPy diagnostics before returning 500:

```python
        except Exception as exc:
            frame = workspace.get_frame(roll_id, frame_id)
            if frame.pipeline.engine == "negpy":
                frame.engines.negpy.diagnostics["error"] = str(exc)
                write_frame_sidecar(
                    workspace.root / "rolls" / roll_id / "frames" / f"{frame_id}.xmp.json",
                    frame,
                )
            jobs.set_failed(job.id, str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc
```

- [ ] **Step 4: Run server tests**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest tests/server -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_server/app.py tests/server/test_api.py
git commit -m "feat: expose processing engine API"
```

---

### Task 7: Frontend Engine Status and Selection

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/api.ts`
- Modify: `web/src/App.tsx`
- Modify: `web/src/App.test.tsx`

- [ ] **Step 1: Replace frontend test with engine behavior coverage**

Replace `web/src/App.test.tsx` with:

```typescript
/// <reference types="@testing-library/jest-dom" />

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

const sampleFrame = {
  frame_id: "IMG_0001",
  status: "unprocessed",
  source: {
    path: "D:/film/IMG_0001.png",
    sha256: "abc",
    camera: null,
    lens: null,
    captured_at: null
  },
  pipeline: {
    engine: "filmcolor",
    tone: {
      style: "faithful",
      exposure: 0,
      contrast: 0.12,
      black_point: 0.004,
      white_point: 0.985
    },
    mask: {
      auto: { rgb_gain: [1, 1, 1], confidence: 0 },
      samples: { film_base: [], gray: [], white: [] }
    }
  },
  engines: {
    negpy: {
      enabled: false,
      version: null,
      source_commit: null,
      backend: "cpu",
      params: { mode: "C41", preset: "default" },
      diagnostics: {}
    }
  },
  exports: [],
  error: null
};

describe("App", () => {
  it("renders disabled NegPy engine when unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/engines") {
          return jsonResponse({
            filmcolor: { available: true },
            negpy: { available: false, experimental: true, backend: "cpu", reason: "missing" }
          });
        }
        if (url === "/api/rolls") {
          return jsonResponse([]);
        }
        return jsonResponse([]);
      })
    );

    render(<App />);

    expect(await screen.findByText("Filmcolor")).toBeInTheDocument();
    expect(screen.getByText("NegPy Experimental")).toBeDisabled();
    expect(screen.getByText("missing")).toBeInTheDocument();
  });

  it("patches frame engine when NegPy is selected", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/engines") {
        return jsonResponse({
          filmcolor: { available: true },
          negpy: { available: true, experimental: true, backend: "cpu", commit: "abc123" }
        });
      }
      if (url === "/api/rolls") {
        return jsonResponse([
          {
            id: "roll-001",
            name: "Roll 001",
            source_dir: "D:/film",
            created_at: "2026-05-02T00:00:00Z",
            defaults: { film_profile: "generic_color_negative", output_style: "faithful", color_space: "sRGB" }
          }
        ]);
      }
      if (url === "/api/rolls/roll-001/frames" && !init) {
        return jsonResponse([sampleFrame]);
      }
      if (url === "/api/rolls/roll-001/frames/IMG_0001/pipeline") {
        return jsonResponse({
          ...sampleFrame,
          pipeline: { ...sampleFrame.pipeline, engine: "negpy" },
          engines: { negpy: { ...sampleFrame.engines.negpy, enabled: true } }
        });
      }
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.click(await screen.findByText("NegPy Experimental"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/rolls/roll-001/frames/IMG_0001/pipeline",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ engine: "negpy", engines: { negpy: { enabled: true } } })
        })
      );
    });
  });
});

function jsonResponse(body: unknown) {
  return Promise.resolve({
    ok: true,
    json: async () => body
  } as Response);
}
```

- [ ] **Step 2: Run frontend test to verify it fails**

Run:

```powershell
Set-Location web
npm.cmd test -- src/App.test.tsx
Set-Location ..
```

Expected: FAIL because `/api/engines` client, engine types, or UI control is missing.

- [ ] **Step 3: Update frontend types**

Modify `web/src/types.ts`.

Add:

```typescript
export type ProcessingEngine = "filmcolor" | "negpy";

export interface EngineStatus {
  filmcolor: { available: true };
  negpy: {
    available: boolean;
    experimental: true;
    backend: "cpu";
    commit?: string;
    reason?: string;
  };
}
```

Add `engine: ProcessingEngine;` to `FrameSidecar["pipeline"]`.

Add `engines` to `FrameSidecar`:

```typescript
  engines: {
    negpy: {
      enabled: boolean;
      version: string | null;
      source_commit: string | null;
      backend: string;
      params: {
        mode: string;
        preset: string;
        density?: number | null;
        grade?: number | null;
        wb_cyan?: number | null;
        wb_magenta?: number | null;
        wb_yellow?: number | null;
      };
      diagnostics: Record<string, unknown>;
    };
  };
```

- [ ] **Step 4: Update API client**

Modify `web/src/api.ts`.

Add imports and functions:

```typescript
import type { EngineStatus, FrameSidecar, OutputStyle, ProcessingEngine, RollMetadata } from "./types";

export async function getEngines(): Promise<EngineStatus> {
  const response = await fetch("/api/engines");
  return readJson(response);
}

export async function setFrameEngine(
  rollId: string,
  frameId: string,
  engine: ProcessingEngine
): Promise<FrameSidecar> {
  const body =
    engine === "negpy"
      ? { engine, engines: { negpy: { enabled: true } } }
      : { engine, engines: { negpy: { enabled: false } } };
  const response = await fetch(`/api/rolls/${rollId}/frames/${frameId}/pipeline`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  return readJson(response);
}
```

- [ ] **Step 5: Update App engine UI**

Modify `web/src/App.tsx`.

Import:

```typescript
import { getEngines, listFrames, listRolls, renderPreview, setFrameEngine, setFrameStyle } from "./api";
import type { EngineStatus, FrameSidecar, OutputStyle, ProcessingEngine, RollMetadata } from "./types";
```

Add state:

```typescript
  const [engines, setEngines] = useState<EngineStatus | null>(null);
```

Load engine status in the first effect:

```typescript
    getEngines()
      .then(setEngines)
      .catch((err: Error) => setError(err.message));
```

Add handler:

```typescript
  async function chooseEngine(engine: ProcessingEngine) {
    if (!selectedRollId || !selectedFrame) return;
    const updated = await setFrameEngine(selectedRollId, selectedFrame.frame_id, engine);
    setFrames((current) =>
      current.map((frame) => (frame.frame_id === updated.frame_id ? updated : frame))
    );
    setPreviewUrl("");
  }
```

Add panel UI before style controls:

```tsx
        <div className="sectionLabel">ENGINE</div>
        <div className="segmented engineSegment">
          <button
            className={(selectedFrame?.pipeline.engine ?? "filmcolor") === "filmcolor" ? "selected" : ""}
            onClick={() => chooseEngine("filmcolor")}
          >
            Filmcolor
          </button>
          <button
            className={selectedFrame?.pipeline.engine === "negpy" ? "selected" : ""}
            disabled={!engines?.negpy.available}
            onClick={() => chooseEngine("negpy")}
          >
            NegPy Experimental
          </button>
        </div>
        {engines?.negpy.available ? (
          <p className="engineNote">NegPy Experimental · CPU backend · {engines.negpy.commit ?? "unknown commit"}</p>
        ) : (
          <p className="engineNote">{engines?.negpy.reason ?? "Checking NegPy availability..."}</p>
        )}
```

Keep existing style controls; do not remove them in this task.

- [ ] **Step 6: Run frontend test and build**

Run:

```powershell
Set-Location web
npm.cmd test -- src/App.test.tsx
npm.cmd run build
Set-Location ..
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/types.ts web/src/api.ts web/src/App.tsx web/src/App.test.tsx
git commit -m "feat: add experimental engine selector"
```

---

### Task 8: Full Verification and Docs Polish

**Files:**
- Modify: `README.md` only if verification reveals missing instructions

- [ ] **Step 1: Run default Python tests**

Run:

```powershell
$env:UV_CACHE_DIR = "D:\filmcolor\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
uv run pytest
```

Expected: PASS with all Python tests passing without installing `--extra negpy`.

- [ ] **Step 2: Run frontend verification**

Run:

```powershell
Set-Location web
npm.cmd test
npm.cmd run build
Set-Location ..
```

Expected: Vitest PASS and Vite build succeeds.

- [ ] **Step 3: Check git submodule status**

Run:

```powershell
git submodule status
```

Expected: one line for `vendor/NegPy` with a commit hash.

- [ ] **Step 4: Commit docs polish if needed**

If README changes were needed:

```powershell
git add README.md
git commit -m "docs: clarify NegPy setup"
```

If no README changes were needed, do not create an empty commit.

---

## Plan Self-Review

Spec coverage:

- Submodule: Task 1.
- Optional dependencies and README/GPL attribution: Task 1.
- Adapter boundary: Task 3.
- Sidecar engine settings and NegPy diagnostics model: Task 2.
- Preview dispatch by engine: Task 4.
- Engine patch persistence: Task 5.
- `GET /api/engines` and API dispatch/failure diagnostics: Task 6.
- Frontend engine selector and unavailable state: Task 7.
- Default tests without real NegPy: Tasks 3, 6, 7, 8.

Deferred by design:

- Real upstream NegPy dependency smoke with actual rendered result.
- Subprocess fallback implementation.
- GPU mode.
- Final TIFF/JPEG NegPy export.
- Full NegPy parameter UI.
