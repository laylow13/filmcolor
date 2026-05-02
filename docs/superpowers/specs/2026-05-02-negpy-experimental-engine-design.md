# NegPy Experimental Engine Design

Date: 2026-05-02

## Goal

Add NegPy as an optional advanced processing engine for Filmcolor. NegPy should be available as an experimental preview backend while the existing Filmcolor pipeline remains the default and continues to work without NegPy installed.

The first version focuses on preview rendering only. Final TIFF/JPEG export through NegPy, full parameter mapping, GPU acceleration, and full NegPy UI parity are deferred.

## Context

Filmcolor currently has a lightweight local color negative conversion pipeline:

- Python core package for image decoding, inversion, mask estimation, and preview rendering.
- FastAPI backend for roll/frame storage, sidecars, preview rendering, and jobs.
- React frontend with a local workbench and basic pipeline controls.

NegPy is an external GPL-3.0 color negative processing project with a more elaborate professional workflow. Its documented pipeline includes:

1. Geometry and crop.
2. Log-space scan normalization.
3. H&D print exposure simulation.
4. Retouching.
5. Lab scanner mode.
6. Toning and paper simulation.

NegPy is not a small algorithm package. It is a full desktop application with loaders, GPU and CPU rendering engines, PyQt UI, ICC support, export services, retouching, and local persistence. The integration must therefore keep a strict adapter boundary.

## Scope

This design includes:

- Add NegPy as `vendor/NegPy` git submodule.
- Add a `negpy` optional dependency path.
- Add `NegPy Experimental` as a selectable processing engine.
- Add a Filmcolor adapter that calls NegPy in-process for preview rendering.
- Force CPU backend for the first integration.
- Prefer NegPy's own file loading path for preview rendering.
- Preserve Filmcolor's default pipeline and existing behavior.
- Record NegPy engine state, commit, backend, and diagnostics in sidecars.
- Expose engine availability through the API.
- Add frontend engine selection UI.

This design does not include:

- Making NegPy the default engine.
- Full NegPy export integration.
- GPU/WGPU integration.
- Complete NegPy parameter UI.
- Automatic mapping of Filmcolor tone/mask controls to NegPy parameters.
- Forking or copying NegPy source into Filmcolor.
- Reimplementing NegPy algorithms directly.

## License Position

NegPy is GPL-3.0. Filmcolor accepts GPL-3.0 or GPL-compatible open-source distribution. The project should still make the dependency explicit:

- Keep NegPy as a submodule instead of copying its source into Filmcolor.
- Document NegPy attribution and license in README.
- Document that enabling `NegPy Experimental` uses GPL-3.0 code from the NegPy project.

## Architecture

NegPy is integrated as a separate processing engine, not as an output style.

```text
filmcolor/
  vendor/
    NegPy/                  # git submodule
  src/
    filmcolor_core/
      negpy_adapter.py       # only module allowed to import NegPy internals
      render.py              # dispatches preview rendering by engine
      models.py              # sidecar engine and NegPy settings
    filmcolor_server/
      app.py                 # engine status and preview dispatch
      storage.py             # sidecar engine updates
  web/
    src/
      App.tsx                # engine selection control
      api.ts                 # engine status API
      types.ts               # engine types
```

### Default Pipeline Remains Independent

Filmcolor's current engine remains the default. If NegPy is missing, not initialized, or fails to import, all existing Filmcolor operations must continue to work.

### Adapter Boundary

Only `filmcolor_core.negpy_adapter` may import or call NegPy internals. Other Filmcolor modules call a stable adapter interface:

```python
class NegPyUnavailable(RuntimeError):
    pass

def get_negpy_status() -> dict:
    ...

def render_negpy_preview(source_path, output_path, settings, max_size=1600) -> dict:
    ...
```

This preserves a fallback route. If in-process import proves unstable, the adapter implementation can switch to a subprocess runner without changing server, storage, or frontend code.

### In-Process First, Subprocess Escape Hatch

The first implementation uses in-process integration:

- Add `vendor/NegPy` to `sys.path` inside the adapter only.
- Import NegPy's `WorkspaceConfig` and CPU rendering path.
- Use NegPy default C-41 settings.
- Write a preview image to the requested output path.

If this fails due to dependency conflicts, desktop import side effects, GPU initialization, or platform issues, replace the adapter internals with a subprocess runner. The public adapter function signatures should not change.

### CPU Backend

First-version NegPy preview rendering is CPU-only. Do not initialize or depend on NegPy's GPU/WGPU path. The engine status should report:

```json
{
  "backend": "cpu",
  "experimental": true
}
```

## Dependency Strategy

NegPy is optional.

Default development setup remains:

```powershell
uv sync --extra dev
```

NegPy-enabled setup becomes:

```powershell
git submodule update --init --recursive
uv sync --extra dev --extra negpy
```

The `negpy` extra should include the runtime dependencies required for the adapter path. Because NegPy's own dependency set is heavy and includes UI/GPU packages, the implementation plan should decide whether to:

- Reference the local submodule as an editable/package dependency when possible.
- Mirror necessary runtime dependencies in Filmcolor's `negpy` extra.
- Keep a clearly documented fallback to a separate NegPy virtual environment if dependency conflicts appear.

## Sidecar Model

Extend frame sidecars with an explicit engine choice and per-engine settings.

Example:

```json
{
  "pipeline": {
    "engine": "filmcolor",
    "version": "0.1.0",
    "raw": {},
    "inversion": {},
    "mask": {},
    "tone": {}
  },
  "engines": {
    "negpy": {
      "enabled": false,
      "version": null,
      "source_commit": null,
      "backend": "cpu",
      "params": {
        "mode": "C41",
        "preset": "default",
        "density": null,
        "grade": null,
        "wb_cyan": null,
        "wb_magenta": null,
        "wb_yellow": null
      },
      "diagnostics": {}
    }
  }
}
```

Rules:

- `pipeline.engine` selects the current preview engine.
- Valid first-version values are `filmcolor` and `negpy`.
- Filmcolor's existing `raw`, `inversion`, `mask`, and `tone` settings remain intact.
- NegPy settings are independent and do not overwrite Filmcolor settings.
- `null` NegPy parameter values mean "use NegPy default".
- `source_commit` records the NegPy submodule commit used for rendering.
- Diagnostics may include adapter type, backend, availability, errors, and selected NegPy metrics.

## Preview Cache

Preview cache keys must include:

- Input file hash.
- Filmcolor pipeline version.
- Selected engine.
- Filmcolor settings hash when using Filmcolor.
- NegPy submodule commit hash when using NegPy.
- NegPy params hash when using NegPy.

This prevents Filmcolor and NegPy previews from reusing each other's cache entries.

## Backend API

### Update Pipeline

Existing frame pipeline patch endpoint should support:

```json
{
  "engine": "negpy"
}
```

It should also support updating the NegPy engine block:

```json
{
  "engines": {
    "negpy": {
      "enabled": true,
      "params": {
        "preset": "default"
      }
    }
  }
}
```

### Render Preview

Existing preview endpoint dispatches by sidecar engine:

```text
POST /api/rolls/{roll_id}/frames/{frame_id}/render-preview
```

Dispatch rules:

- `filmcolor`: current `render_preview_file`.
- `negpy`: `render_negpy_preview`.

If NegPy fails, the API should return a clear error and persist diagnostics into the sidecar. Do not silently fall back to Filmcolor, because the user should know whether the displayed preview is actually a NegPy result.

### Engine Status

Add:

```text
GET /api/engines
```

Example response when available:

```json
{
  "filmcolor": {
    "available": true
  },
  "negpy": {
    "available": true,
    "experimental": true,
    "backend": "cpu",
    "commit": "abc123"
  }
}
```

Example response when unavailable:

```json
{
  "filmcolor": {
    "available": true
  },
  "negpy": {
    "available": false,
    "experimental": true,
    "backend": "cpu",
    "reason": "NegPy dependencies are not installed. Run uv sync --extra negpy."
  }
}
```

## Frontend UI

Add an engine segmented control near the top of the parameter panel:

```text
Filmcolor | NegPy Experimental
```

Behavior:

- `Filmcolor` is selected by default.
- `NegPy Experimental` is visible but disabled when unavailable.
- Unavailable state shows the reason returned by `GET /api/engines`.
- Selecting `NegPy Experimental` patches `pipeline.engine = "negpy"`.
- The preview button renders through the selected engine.
- NegPy mode shows an experimental label and CPU backend status.
- Filmcolor-specific mask/tone controls should not imply that they affect NegPy output.
- First version shows minimal NegPy information only: mode `C41`, preset `default`, backend `cpu`, commit/version.

If NegPy preview fails:

- Show the error near the preview or engine control.
- Offer an explicit "Switch back to Filmcolor" action.
- Keep the selected engine as `negpy` unless the user switches it back.

## Implementation Milestones

### M1: Submodule and Documentation

- Add `vendor/NegPy` submodule.
- Add README instructions for submodule initialization and NegPy-enabled setup.
- Add GPL/NegPy attribution.
- Add tests for missing submodule behavior where possible.

### M2: Adapter

- Add `filmcolor_core.negpy_adapter`.
- Add `NegPyUnavailable`.
- Add `get_negpy_status`.
- Add `render_negpy_preview`.
- Force CPU behavior.
- Prefer NegPy's own loader path.
- Add tests using monkeypatch or fake NegPy modules so core tests do not require heavy NegPy dependencies.

### M3: Sidecar and Cache

- Add `PipelineSettings.engine`.
- Add engine-specific NegPy settings models.
- Add sidecar round-trip tests.
- Add cache-key logic that includes engine and NegPy identity.

### M4: API

- Add `GET /api/engines`.
- Extend pipeline patching for `engine` and `engines.negpy`.
- Dispatch preview rendering by engine.
- Persist NegPy diagnostics on failure.
- Add API tests for available/unavailable NegPy states and adapter dispatch.

### M5: Frontend

- Add engine status API client.
- Add engine segmented control.
- Disable NegPy when unavailable.
- Patch selected engine on user choice.
- Render preview through selected engine.
- Add frontend tests for engine visibility, disabled state, and patch behavior.

## Testing Strategy

Default test path:

```powershell
uv sync --extra dev
uv run pytest
Set-Location web
npm.cmd test
npm.cmd run build
```

NegPy-enabled manual verification:

```powershell
git submodule update --init --recursive
uv sync --extra dev --extra negpy
uv run pytest
```

Test requirements:

- Default tests must pass without NegPy installed.
- NegPy unavailable state must be tested.
- Adapter success path should be tested with fakes or monkeypatching.
- No test should require GPU.
- No frontend test should require a real NegPy installation.

## Acceptance Criteria

- Filmcolor defaults continue to work without NegPy.
- `GET /api/engines` reports Filmcolor available and NegPy status.
- Sidecars can select `pipeline.engine = "negpy"`.
- NegPy settings round-trip independently from Filmcolor settings.
- Preview rendering dispatches to NegPy adapter when selected.
- NegPy failures are visible and persisted as diagnostics.
- UI clearly marks NegPy as experimental and CPU-backed.
- Frontend and backend tests pass in the default setup.
