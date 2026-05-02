# Filmcolor Polish & Hardening Design

Date: 2026-05-02

## Goal

Harden the codebase, add developer automation, and polish the frontend after completing the NegPy experimental engine integration.

## Scope

Three independent workstreams, ordered by priority:

### 2. Code Robustness

R1 — Thread-safe negpy module import
- Add `threading.Lock` to `_import_negpy_modules()` in `negpy_adapter.py`
- Prevents race condition when `sys.path.insert`/`remove` called from multiple threads

R2 — Short commit hash
- Change `_negpy_commit()` to use `rev-parse --short=7` instead of `rev-parse HEAD`
- 7-char hash displayed in frontend engine note instead of 40-char full hash

R3 — Resilient engine status endpoint
- Wrap `get_negpy_status()` call in `GET /api/engines` with try/except
- On unexpected failure, return `available: false` with reason instead of 500

R4 — Use workspace method for sidecar path
- Replace hardcoded `workspace.root / "rolls" / roll_id / "frames" / f"{frame_id}.xmp.json"` in `app.py` exception handler with `workspace._frame_path(roll_id, frame_id)`

### 3. Developer Experience

D1 — Pre-commit hooks
- Create `.pre-commit-config.yaml` with ruff lint and ruff format
- Lint blocks commit on errors; format auto-fixes

D2 — CI pipeline
- Create `.github/workflows/ci.yml`
- Runs on push/PR to main: Python tests (uv run pytest), frontend tests (npm test), frontend build (npm run build)

D3 — Fix ruff target version
- `pyproject.toml`: `target-version = "py312"` → `"py313"` (matches requires-python)

D4 — Coverage threshold
- `pyproject.toml`: add `[tool.coverage.report]` with `fail_under = 80`
- `pytest-cov` already installed, just not configured

### 4. Frontend Polish

U1 — Loading indicator
- Add a thin progress bar at top of shell during initial data fetch
- Uses existing `engines === null` state as loading signal

U2 — Dismissible error banner
- Replace `<p className="error">` with a banner that includes a close button
- Error state persists until dismissed

U3 — Preview loading state
- During render-preview POST, show pulsating placeholder in preview area
- "Rendering..." text with CSS pulse animation

U4 — Hide Filmcolor readouts when NegPy selected
- When `engine === "negpy"`, hide Mask confidence/Exposure/Contrast readouts
- Show NegPy readout instead: "Backend" (cpu), "Commit" (short hash), "Adapter" (in_process)
- Source data from `engines.negpy` in frame sidecar
- When engine is filmcolor, show existing readouts as before

U5 — Fix engine grid
- CSS: `.engineSegment` uses `grid-template-columns: repeat(2, 1fr)` instead of inheriting 3 columns from `.segmented`

## Files Changed

```
src/filmcolor_core/negpy_adapter.py   # R1, R2
src/filmcolor_server/app.py           # R3, R4
pyproject.toml                        # D3, D4
.pre-commit-config.yaml               # D1 (new)
.github/workflows/ci.yml              # D2 (new)
web/src/App.tsx                       # U2, U4
web/src/App.test.tsx                  # U2, U4
web/src/styles.css                    # U1, U3, U5
```

## Non-Scope

- R5 (render return type) and R6 (pipeline sample validation) — not included; R5 is cosmetic, R6 already has bounds checks
- Prettier or ESLint in pre-commit — ruff covers Python; frontend linting deferred
- before/after comparison view — belongs in M4 interactive correction
- Loading skeleton for frame list — covered by U1's top bar approach

## Testing

- Existing 27 Python + 2 frontend tests must continue to pass
- R1-R4 are internal changes that existing tests exercise indirectly
- U2 error banner test: verify dismiss behavior in App.test.tsx
- U4 NegPy readout test: verify readout content when engine is negpy
