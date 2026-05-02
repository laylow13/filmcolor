# Filmcolor NegPy Experimental Engine — Walkthrough

Date: 2026-05-02

## Status: Complete

All 8 tasks of the [NegPy Experimental Engine implementation plan](superpowers/plans/2026-05-02-negpy-experimental-engine.md) are implemented and merged to `main`.

## Task Summary

| Task | Description | Status |
|------|-------------|--------|
| 1 | Add NegPy submodule, pyproject.toml `negpy` extra, README docs | Done |
| 2 | Sidecar engine models (`ProcessingEngine`, `NegPyEngineSettings`, `EngineSettings`) | Done |
| 3 | NegPy adapter boundary (`negpy_adapter.py`, fake-tested) | Done |
| 4 | Preview dispatch by engine in `render.py` | Done |
| 5 | Storage engine block persistence (`update_frame_engines`) | Done |
| 6 | `GET /api/engines`, PATCH extension, failure diagnostics | Done |
| 7 | Frontend engine segmented control with unavailable-state messaging | Done |
| 8 | Full verification (27 Python + 2 frontend tests, submodule check) | Done |

## Architecture

```
filmcolor/
  vendor/NegPy/                       # git submodule (GPL-3.0)
  src/filmcolor_core/
    models.py                          # ProcessingEngine, NegPyEngineSettings, etc.
    negpy_adapter.py                   # only module allowed to import NegPy
    render.py                          # dispatches render by pipeline.engine
  src/filmcolor_server/
    app.py                             # GET /api/engines, preview dispatch, diagnostics
    storage.py                         # update_frame_engines()
  web/src/
    App.tsx                            # ENGINE segmented control
    api.ts                             # getEngines(), setFrameEngine()
    types.ts                           # ProcessingEngine, EngineStatus
```

## Key Decisions

- **Adapter boundary**: Only `negpy_adapter.py` touches NegPy internals. All other modules call the stable public interface: `get_negpy_status()` and `render_negpy_preview()`.
- **ImageProcessor path**: Uses NegPy's `ImageProcessor` (CPU pipeline) rather than the original plan's `DarkroomEngine`. Approved in Codex review.
- **sys.path hygiene**: `_import_negpy_modules()` temporarily adds `vendor/NegPy` to `sys.path` only during import, removes it afterward.
- **CPU-only**: First integration forces CPU backend. GPU/WGPU initialization is avoided.

## How to Enable NegPy

```powershell
git submodule update --init --recursive
uv sync --extra dev --extra negpy
```

When the submodule or dependencies are missing, `NegPy Experimental` shows as disabled with a reason message.

## Running

Backend: `uv run uvicorn filmcolor_server.app:app --reload --host 127.0.0.1 --port 8000`
Frontend: `cd web && npm run dev` → http://127.0.0.1:5173

## Tests

- **27 Python tests** — all pass without NegPy installed (fake-tested adapter)
- **2 frontend tests** — cover unavailable state (disabled button) and available state (enabled button)
- **Vite build** passes TypeScript compilation + production bundle

## Deferred

These are intentionally not in this delivery:

- Real NegPy integration smoke test (manual verification path available)
- Subprocess fallback runner
- GPU/WGPU mode
- Full NegPy parameter UI mapping
- NegPy TIFF/JPEG export
- Frontend build step verification
