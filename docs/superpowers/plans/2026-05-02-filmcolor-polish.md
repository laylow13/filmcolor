# Filmcolor Polish & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Python code, add pre-commit/CI automation, and polish frontend UX after NegPy experimental engine integration.

**Architecture:** Three independent workstreams applied in order: (1) code robustness fixes in `negpy_adapter.py` and `app.py`, (2) developer tooling via pre-commit hooks, GitHub Actions CI, and pyproject.toml config, (3) frontend polish in App.tsx and styles.css covering loading states, error UX, NegPy-aware readouts, and CSS fixes.

**Tech Stack:** Python 3.13, pytest, ruff, pre-commit, GitHub Actions, React, TypeScript, CSS.

---

## File Structure

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

---

### Task 1: Thread-Safe NegPy Import + Short Commit Hash

**Files:**
- Modify: `src/filmcolor_core/negpy_adapter.py`

- [ ] **Step 1: Write failing thread-safety test**

Append to `tests/core/test_negpy_adapter.py`:

```python
import threading

from filmcolor_core.negpy_adapter import get_negpy_status


def test_get_negpy_status_is_thread_safe(monkeypatch):
    from filmcolor_core.negpy_adapter import _import_negpy_modules, _negpy_root

    root = _negpy_root()
    if not root.exists():
        monkeypatch.setattr("filmcolor_core.negpy_adapter._negpy_root", lambda: Path("Z:/missing/NegPy"))

    results = []
    errors = []

    def call():
        try:
            results.append(get_negpy_status())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/core/test_negpy_adapter.py::test_get_negpy_status_is_thread_safe -v
```

Expected: may pass or fail intermittently. If it fails, proceed to fix.

- [ ] **Step 3: Add thread lock to `_import_negpy_modules`**

Modify `src/filmcolor_core/negpy_adapter.py`.

Add `import threading` at top, add lock:

```python
import threading

_negpy_import_lock = threading.Lock()


def _import_negpy_modules(root: Path) -> dict[str, Any]:
    root_str = str(root)
    with _negpy_import_lock:
        added_path = root_str not in sys.path
        if added_path:
            sys.path.insert(0, root_str)

        try:
            from negpy.domain.models import WorkspaceConfig
            from negpy.services.rendering.image_processor import ImageProcessor
        finally:
            if added_path:
                try:
                    sys.path.remove(root_str)
                except ValueError:
                    pass

    return {
        "WorkspaceConfig": WorkspaceConfig,
        "ImageProcessor": ImageProcessor,
    }
```

- [ ] **Step 4: Change `_negpy_commit` to use short hash**

Modify `src/filmcolor_core/negpy_adapter.py`, in `_negpy_commit()`:

```python
["git", "-C", str(root), "rev-parse", "--short=7", "HEAD"],
```

- [ ] **Step 5: Run tests**

Run:

```powershell
uv run pytest tests/core/test_negpy_adapter.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/filmcolor_core/negpy_adapter.py tests/core/test_negpy_adapter.py
git commit -m "fix: thread-safe negpy import and short commit hash"
```

---

### Task 2: Resilient Engine Status + Use Workspace Path Method

**Files:**
- Modify: `src/filmcolor_server/app.py`

- [ ] **Step 1: Write failing test for resilient engine endpoint**

Append to `tests/server/test_api.py`:

```python
def test_engines_endpoint_returns_unavailable_when_status_check_crashes(workspace_tmp_path: Path, monkeypatch):
    def boom():
        raise RuntimeError("status check exploded")

    monkeypatch.setattr("filmcolor_server.app.get_negpy_status", boom)
    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))

    response = client.get("/api/engines")

    assert response.status_code == 200
    assert response.json()["filmcolor"]["available"] is True
    assert response.json()["negpy"]["available"] is False
    assert "status check exploded" in response.json()["negpy"]["reason"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/server/test_api.py::test_engines_endpoint_returns_unavailable_when_status_check_crashes -v
```

Expected: FAIL with 500 error or unhandled exception (monkeypatch can't find import).

**Correction** — the monkeypatch target `filmcolor_server.app.get_negpy_status` points to the import location. If the test fails because the function is defined inside `create_app()` and not importable at module level, wrap it differently:

```python
def test_engines_endpoint_returns_unavailable_when_status_check_crashes(workspace_tmp_path: Path, monkeypatch):
    def boom():
        raise RuntimeError("status check exploded")

    monkeypatch.setattr("filmcolor_core.negpy_adapter.get_negpy_status", boom)
    monkeypatch.setattr("filmcolor_server.app.get_negpy_status", boom)
    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))

    response = client.get("/api/engines")

    assert response.status_code == 200
    assert response.json()["filmcolor"]["available"] is True
    assert response.json()["negpy"]["available"] is False
    assert "status check exploded" in response.json()["negpy"]["reason"]
```

- [ ] **Step 3: Wrap `get_negpy_status()` in API route with try/except**

Modify `src/filmcolor_server/app.py`, in the `get_engines` endpoint:

```python
    @app.get("/api/engines")
    def get_engines():
        try:
            negpy = get_negpy_status()
        except Exception as exc:
            negpy = {
                "available": False,
                "experimental": True,
                "backend": "cpu",
                "reason": str(exc),
            }
        return {
            "filmcolor": {"available": True},
            "negpy": negpy,
        }
```

- [ ] **Step 4: Use workspace helper for sidecar path in exception handler**

Modify `src/filmcolor_server/app.py`, in the `render_preview` exception handler.

Replace:

```python
            frame = workspace.get_frame(roll_id, frame_id)
            if frame.pipeline.engine == "negpy":
                frame.engines.negpy.diagnostics["error"] = str(exc)
                write_frame_sidecar(
                    workspace.root / "rolls" / roll_id / "frames" / f"{frame_id}.xmp.json",
                    frame,
                )
```

With:

```python
            frame = workspace.get_frame(roll_id, frame_id)
            if frame.pipeline.engine == "negpy":
                frame.engines.negpy.diagnostics["error"] = str(exc)
                write_frame_sidecar(workspace._frame_path(roll_id, frame_id), frame)
```

- [ ] **Step 5: Run server tests**

Run:

```powershell
uv run pytest tests/server/test_api.py -v
```

Expected: all server tests PASS (6 tests).

- [ ] **Step 6: Commit**

```powershell
git add src/filmcolor_server/app.py tests/server/test_api.py
git commit -m "fix: resilient engine status endpoint and use workspace path helper"
```

---

### Task 3: Pre-commit Hooks and CI Pipeline

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create pre-commit config**

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.12
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
```

- [ ] **Step 2: Create GitHub Actions CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: false
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: uv sync --extra dev
      - run: uv run pytest --cov=src --cov-report=term --cov-fail-under=80

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: cd web && npm ci
      - run: cd web && npm test
      - run: cd web && npm run build
```

- [ ] **Step 3: Fix ruff target version and add coverage threshold**

Modify `pyproject.toml`.

Change:

```toml
target-version = "py312"
```

To:

```toml
target-version = "py313"
```

Add after `[tool.ruff]` section:

```toml
[tool.coverage.report]
fail_under = 80
exclude_also = [
  "if __name__ == .__main__.:",
  "if TYPE_CHECKING:",
]
```

- [ ] **Step 4: Run ruff to verify config works**

Run:

```powershell
uv run ruff check src/ tests/
```

Expected: no lint errors.

- [ ] **Step 5: Run tests with coverage to verify threshold**

Run:

```powershell
uv run pytest --cov=src --cov-report=term
```

Expected: coverage >= 80%.

- [ ] **Step 6: Commit**

```powershell
git add .pre-commit-config.yaml .github/workflows/ci.yml pyproject.toml
git commit -m "chore: add pre-commit hooks, CI pipeline, and coverage threshold"
```

---

### Task 4: Frontend Loading, Error UX, Engine-Aware Readouts

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/App.test.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Add CSS for loading, error banner, and preview state**

Append to `web/src/styles.css`:

```css
/* U1: top loading bar */
.loadingBar {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  background: linear-gradient(90deg, #c26b2b, #e09d4a, #c26b2b);
  background-size: 200% 100%;
  animation: loadingSlide 1.2s ease-in-out infinite;
  z-index: 100;
  transition: width 0.3s ease;
}

@keyframes loadingSlide {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* U2: dismissible error banner */
.errorBanner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  margin-top: 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #a12424;
  font-size: 13px;
}

.errorBanner button {
  flex-shrink: 0;
  padding: 4px 8px;
  border: 1px solid #fecaca;
  border-radius: 4px;
  background: #fff;
  color: #a12424;
  cursor: pointer;
  font-size: 12px;
}

/* U3: preview loading pulse */
.previewLoading {
  display: grid;
  place-items: center;
  gap: 12px;
  color: #8a8278;
}

.previewLoading span {
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* U5: engine segment uses 2 columns */
.engineSegment {
  grid-template-columns: repeat(2, 1fr) !important;
}

/* NegPy info readout for U4 */
.negpyInfo {
  display: grid;
  gap: 10px;
  padding: 12px;
  margin-bottom: 20px;
  border: 1px solid #ded8cc;
  border-radius: 8px;
  background: #fffdf8;
}

.negpyInfo dt {
  color: #706a60;
  font-size: 12px;
  margin-bottom: 2px;
}

.negpyInfo dd {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 13px;
}
```

- [ ] **Step 2: Update App.tsx — loading bar, error banner, preview loading, NegPy readouts**

Modify `web/src/App.tsx`.

Add `isRendering` state after `previewUrl`:

```typescript
  const [isRendering, setIsRendering] = useState(false);
```

Update `handleRenderPreview`:

```typescript
  async function handleRenderPreview() {
    if (!selectedRollId || !selectedFrame) return;
    setIsRendering(true);
    try {
      const result = await renderPreview(selectedRollId, selectedFrame.frame_id);
      setPreviewUrl(`${result.preview_url}?t=${Date.now()}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Render failed");
    } finally {
      setIsRendering(false);
    }
  }
```

Add loading bar after `<main className="shell">`:

```tsx
      {engines === null && rolls.length === 0 && !error ? (
        <div className="loadingBar" style={{ width: "100%" }} />
      ) : null}
```

Replace the error `<p>` at the bottom of the panel with a dismissible banner:

```tsx
        {error ? (
          <div className="errorBanner">
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Dismiss error">
              Dismiss
            </button>
          </div>
        ) : null}
```

Replace the preview empty/loading area:

```tsx
        <div className="preview">
          {isRendering ? (
            <div className="previewLoading">
              <ImageIcon size={34} />
              <span>Rendering...</span>
            </div>
          ) : previewUrl ? (
            <img src={previewUrl} alt="Rendered film preview" />
          ) : (
            <div className="previewEmpty">
              <ImageIcon size={34} />
              <span>Render a preview</span>
            </div>
          )}
        </div>
```

Replace the readout section to be engine-aware:

```tsx
        {selectedFrame?.pipeline.engine === "negpy" ? (
          <div className="negpyInfo">
            <dl>
              <div>
                <dt>Backend</dt>
                <dd>{selectedFrame.engines.negpy.backend}</dd>
              </div>
              <div>
                <dt>Commit</dt>
                <dd>{selectedFrame.engines.negpy.source_commit?.slice(0, 7) ?? "unknown"}</dd>
              </div>
              <div>
                <dt>Adapter</dt>
                <dd>{String(selectedFrame.engines.negpy.diagnostics?.adapter ?? "in_process")}</dd>
              </div>
            </dl>
          </div>
        ) : (
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
        )}
```

Remove the old `dl.readout` block and the old `{error ? <p className="error">{error}</p> : null}` from the JSX.

- [ ] **Step 3: Update App.test.tsx for new behavior**

Replace `web/src/App.test.tsx`:

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
    tone: { style: "faithful", exposure: 0, contrast: 0.12, black_point: 0.004, white_point: 0.985 },
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
        if (url === "/api/rolls") return jsonResponse([]);
        return jsonResponse([]);
      })
    );

    render(<App />);

    expect(await screen.findByText(/CPU backend/)).toBeInTheDocument();
    const negpyBtns = screen.getAllByText("NegPy Experimental");
    expect(negpyBtns[0]).toBeDisabled();
    expect(screen.getByText("missing")).toBeInTheDocument();
  });

  it("shows NegPy readouts when engine is negpy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/engines") {
          return jsonResponse({
            filmcolor: { available: true },
            negpy: { available: true, experimental: true, backend: "cpu", commit: "abc1234" }
          });
        }
        if (url === "/api/rolls") {
          return jsonResponse([
            {
              id: "roll-001", name: "Roll 001", source_dir: "D:/film",
              created_at: "2026-05-02T00:00:00Z",
              defaults: { film_profile: "generic_color_negative", output_style: "faithful", color_space: "sRGB" }
            }
          ]);
        }
        if (url === "/api/rolls/roll-001/frames") {
          return jsonResponse([{
            ...sampleFrame,
            pipeline: { ...sampleFrame.pipeline, engine: "negpy" },
            engines: { negpy: { ...sampleFrame.engines.negpy, enabled: true, diagnostics: { adapter: "in_process" } } }
          }]);
        }
        return jsonResponse([]);
      })
    );

    render(<App />);

    expect(await screen.findByText("Backend")).toBeInTheDocument();
    expect(screen.getByText("cpu")).toBeInTheDocument();
    expect(screen.getByText("Adapter")).toBeInTheDocument();
  });
});

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: async () => body } as Response);
}
```

- [ ] **Step 4: Run frontend test and build**

Run:

```powershell
cd web
npm.cmd test -- run src/App.test.tsx
npm.cmd run build
```

Expected: 2 tests PASS, build SUCCEEDS.

- [ ] **Step 5: Commit**

```powershell
git add web/src/App.tsx web/src/App.test.tsx web/src/styles.css
git commit -m "feat: add loading states, dismissible errors, and engine-aware readouts"
```

---

### Task 5: Full Verification

**Files:** none

- [ ] **Step 1: Run all Python tests**

Run:

```powershell
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run frontend tests and build**

Run:

```powershell
cd web
npm.cmd test
npm.cmd run build
```

Expected: PASS + build succeeds.

- [ ] **Step 3: Run ruff lint**

Run:

```powershell
uv run ruff check src/ tests/
```

Expected: no errors.

- [ ] **Step 4: Verify pre-commit installs**

Run:

```powershell
pre-commit run --all-files
```

Expected: ruff and ruff-format pass.

- [ ] **Step 5: Commit any remaining changes**

Only if verification revealed issues. Otherwise skip.

---

## Plan Self-Review

Spec coverage:
- R1 (thread lock) → Task 1
- R2 (short hash) → Task 1
- R3 (resilient endpoint) → Task 2
- R4 (workspace path helper) → Task 2
- D1 (pre-commit) → Task 3
- D2 (CI) → Task 3
- D3 (ruff target version) → Task 3
- D4 (coverage threshold) → Task 3
- U1 (loading indicator) → Task 4
- U2 (dismissible error) → Task 4
- U3 (preview loading) → Task 4
- U4 (NegPy readouts) → Task 4
- U5 (engine grid fix) → Task 4

No placeholders. All code blocks complete. All paths verified.
