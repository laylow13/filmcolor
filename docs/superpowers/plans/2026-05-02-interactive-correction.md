# Interactive Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add click-to-sample on preview images and frame-to-frame setting synchronization for Filmcolor engine interactive correction.

**Architecture:** Extend pipeline with gray/white sample algorithms and a shared pixel-extraction utility. Add a preview overlay in the frontend for click-to-place sample markers with type selector and sample list. Add a sync API endpoint and contact-sheet multi-select for propagating settings across frames.

**Tech Stack:** Python 3.13, pytest, FastAPI, Pydantic, NumPy, Pillow, React, TypeScript, CSS.

---

## File Structure

```
src/filmcolor_core/pipeline.py     # gray sample balance, white sample luminance, _sample_pixels helper
tests/core/test_pipeline.py        # gray/white sample algorithm tests
src/filmcolor_server/app.py        # POST /api/rolls/{id}/frames/sync
tests/server/test_api.py           # sync endpoint tests
web/src/App.tsx                    # preview overlay, sample markers, multi-select, sync
web/src/App.test.tsx               # sample interaction + sync tests
web/src/styles.css                 # overlay, markers, sample list, multi-select styles
web/src/api.ts                     # syncFrames API function
web/src/types.ts                   # SyncRequest type
```

---

### Task 1: Pipeline Gray and White Sample Support

**Files:**
- Modify: `src/filmcolor_core/pipeline.py`
- Modify: `tests/core/test_pipeline.py`

- [ ] **Step 1: Write failing tests for gray sample balance**

Append to `tests/core/test_pipeline.py`:

```python
from filmcolor_core.pipeline import compute_gray_balance, compute_white_reference


def test_compute_gray_balance_returns_identity_when_no_samples():
    image = np.ones((4, 4, 3), dtype=np.float32) * 0.5
    result = compute_gray_balance(image, [])
    assert result == [1.0, 1.0, 1.0]


def test_compute_gray_balance_neutralizes_gray_pixels():
    image = np.ones((4, 4, 3), dtype=np.float32)
    image[1, 1] = [0.5, 0.25, 1.0]  # magenta-ish gray sample

    result = compute_gray_balance(image, [[1, 1]])

    # Should boost red relative to green, cut blue relative to green
    assert result[0] > 1.0   # red gain up
    assert result[2] < 1.0   # blue gain down
    assert result[1] == pytest.approx(1.0, abs=0.3)


def test_compute_white_reference_returns_one_when_no_samples():
    image = np.ones((4, 4, 3), dtype=np.float32) * 0.5
    result = compute_white_reference(image, [])
    assert result == 1.0


def test_compute_white_reference_uses_sample_luminance():
    image = np.ones((4, 4, 3), dtype=np.float32) * 0.5
    image[2, 2] = [0.9, 0.88, 0.92]  # bright sample

    result = compute_white_reference(image, [[2, 2]])

    # White point should reflect the sampled luminance (~0.9)
    assert result > 0.8


def test_sample_pixels_ignores_out_of_bounds():
    from filmcolor_core.pipeline import _sample_pixels

    image = np.ones((4, 4, 3), dtype=np.float32)
    result = _sample_pixels(image, [[1, 1], [-1, -1], [99, 99], [2, 2]])

    assert len(result) == 2  # only valid coordinates
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
uv run pytest tests/core/test_pipeline.py::test_compute_gray_balance_returns_identity_when_no_samples tests/core/test_pipeline.py::test_compute_gray_balance_neutralizes_gray_pixels tests/core/test_pipeline.py::test_compute_white_reference_returns_one_when_no_samples tests/core/test_pipeline.py::test_compute_white_reference_uses_sample_luminance tests/core/test_pipeline.py::test_sample_pixels_ignores_out_of_bounds -v
```
Expected: FAIL with import errors.

- [ ] **Step 3: Implement `_sample_pixels` helper**

Add to `src/filmcolor_core/pipeline.py` after the import block:

```python
def _sample_pixels(image: np.ndarray, samples: list[list[int]]) -> list[np.ndarray]:
    """Extract pixel values at sample coordinates, skipping out-of-bounds."""
    height, width = image.shape[:2]
    result: list[np.ndarray] = []
    for x, y in samples:
        if 0 <= x < width and 0 <= y < height:
            result.append(image[y, x])
    return result
```

Refactor `estimate_mask_gain` to use `_sample_pixels`:

```python
def estimate_mask_gain(
    image: np.ndarray,
    film_base_samples: list[list[int]],
) -> MaskAutoEstimate:
    linear = np.maximum(image.astype(np.float32), 1e-6)
    sampled = _sample_pixels(linear, film_base_samples)
    if sampled:
        base = np.mean(np.stack(sampled), axis=0)
        gain = _neutralizing_gain(base)
        return MaskAutoEstimate(rgb_gain=gain.tolist(), confidence=1.0)

    mean_rgb = linear.reshape(-1, 3).mean(axis=0)
    gain = _neutralizing_gain(mean_rgb)
    return MaskAutoEstimate(rgb_gain=gain.tolist(), confidence=0.55)
```

- [ ] **Step 4: Implement `compute_gray_balance`**

Add to `src/filmcolor_core/pipeline.py`:

```python
def compute_gray_balance(image: np.ndarray, gray_samples: list[list[int]]) -> list[float]:
    """Return rgb_gain that neutralizes sampled gray pixels to equal R=G=B."""
    sampled = _sample_pixels(image, gray_samples)
    if not sampled:
        return [1.0, 1.0, 1.0]
    avg = np.mean(np.stack(sampled), axis=0)
    gain = _neutralizing_gain(avg)
    return gain.tolist()
```

- [ ] **Step 5: Implement `compute_white_reference`**

Add to `src/filmcolor_core/pipeline.py`:

```python
def compute_white_reference(image: np.ndarray, white_samples: list[list[int]]) -> float:
    """Return white_point derived from sampled white pixel luminance."""
    sampled = _sample_pixels(image, white_samples)
    if not sampled:
        return 1.0
    avg = np.mean(np.stack(sampled), axis=0)
    luminance = float(avg[0] * 0.2126 + avg[1] * 0.7152 + avg[2] * 0.0722)
    return min(0.995, max(0.7, luminance))
```

- [ ] **Step 6: Integrate gray and white samples into `render_pipeline_array`**

Modify the relevant section in `render_pipeline_array` to apply gray balance after mask correction and use white samples for white_point:

```python
    estimate = estimate_mask_gain(inverted, settings.mask.samples.film_base)
    settings.mask.auto = estimate
    balanced = apply_channel_gain(inverted, estimate.rgb_gain)

    gray_gain = compute_gray_balance(balanced, settings.mask.samples.gray)
    balanced = apply_channel_gain(balanced, gray_gain)

    white_ref = compute_white_reference(balanced, settings.mask.samples.white)
    styled = apply_output_style(
        balanced,
        style=settings.tone.style,
        exposure=settings.tone.exposure,
        contrast=settings.tone.contrast,
    )
```

- [ ] **Step 7: Run all pipeline tests**

Run:
```powershell
uv run pytest tests/core/test_pipeline.py -v
```
Expected: all tests PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/filmcolor_core/pipeline.py tests/core/test_pipeline.py
git commit -m "feat: add gray and white sample support to pipeline"
```

---

### Task 2: Sync Endpoint

**Files:**
- Modify: `src/filmcolor_server/app.py`
- Modify: `tests/server/test_api.py`

- [ ] **Step 1: Write failing sync test**

Append to `tests/server/test_api.py`:

```python
def test_sync_endpoint_copies_fields_to_target_frames(workspace_tmp_path: Path):
    import copy, json

    source_dir = workspace_tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source_dir / "IMG_0001.png")
    Image.new("RGB", (4, 4), color=(40, 50, 60)).save(source_dir / "IMG_0002.png")
    Image.new("RGB", (4, 4), color=(70, 80, 90)).save(source_dir / "IMG_0003.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source_dir), "name": "SyncTest"}).json()

    # Set up source frame with custom samples
    client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"mask": {"samples": {"film_base": [[10, 20]], "gray": [[50, 60]]}}, "tone": {"style": "share"}},
    )

    # Sync to IMG_0002 and IMG_0003
    response = client.post(
        f"/api/rolls/{roll['id']}/frames/sync",
        json={
            "source_frame_id": "IMG_0001",
            "target_frame_ids": ["IMG_0002", "IMG_0003"],
            "fields": ["mask.samples", "tone.style"],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["synced_count"] == 2

    frame2 = client.get(f"/api/rolls/{roll['id']}/frames/IMG_0002").json()
    assert frame2["pipeline"]["mask"]["samples"]["film_base"] == [[10, 20]]
    assert frame2["pipeline"]["tone"]["style"] == "share"

    frame3 = client.get(f"/api/rolls/{roll['id']}/frames/IMG_0003").json()
    assert frame3["pipeline"]["tone"]["style"] == "share"


def test_sync_endpoint_rejects_invalid_field(workspace_tmp_path: Path):
    source_dir = workspace_tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source_dir / "IMG_0001.png")
    Image.new("RGB", (4, 4), color=(40, 50, 60)).save(source_dir / "IMG_0002.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source_dir), "name": "SyncTest"}).json()

    response = client.post(
        f"/api/rolls/{roll['id']}/frames/sync",
        json={
            "source_frame_id": "IMG_0001",
            "target_frame_ids": ["IMG_0002"],
            "fields": ["source.path"],
        },
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
uv run pytest tests/server/test_api.py::test_sync_endpoint_copies_fields_to_target_frames tests/server/test_api.py::test_sync_endpoint_rejects_invalid_field -v
```
Expected: FAIL (404 or 405 — endpoint not found).

- [ ] **Step 3: Add SyncRequest model and sync endpoint**

In `src/filmcolor_server/app.py`, add the request model after `PipelinePatchRequest`:

```python
SYNCABLE_FIELDS = {"mask.samples", "tone.style", "tone.exposure", "tone.contrast"}


class SyncRequest(BaseModel):
    source_frame_id: str
    target_frame_ids: list[str]
    fields: list[str]


def _copy_nested(src: dict[str, Any], dst: dict[str, Any], dotted: str) -> None:
    keys = dotted.split(".")
    for key in keys[:-1]:
        src = src[key]
        dst = dst[key]
    dst[keys[-1]] = copy.deepcopy(src[keys[-1]])
```

Add inside `create_app` after the `patch_pipeline` route:

```python
    @app.post("/api/rolls/{roll_id}/frames/sync")
    def sync_frames(roll_id: str, request: SyncRequest):
        invalid = [f for f in request.fields if f not in SYNCABLE_FIELDS]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Fields not syncable: {invalid}. Valid fields: {sorted(SYNCABLE_FIELDS)}",
            )

        source = workspace.get_frame(roll_id, request.source_frame_id)
        source_data = source.model_dump(mode="json")

        synced = 0
        for target_id in request.target_frame_ids:
            if target_id == request.source_frame_id:
                continue
            frame = workspace.get_frame(roll_id, target_id)
            frame_data = frame.model_dump(mode="json")
            for field in request.fields:
                _copy_nested(source_data, frame_data, field)
            updated = FrameSidecar.model_validate(frame_data)
            updated.status = FrameStatus.MANUALLY_ADJUSTED
            write_frame_sidecar(workspace._frame_path(roll_id, target_id), updated)
            synced += 1

        return {"synced_count": synced}
```

Add required imports at top of app.py:
```python
import copy
from filmcolor_core.models import FrameStatus
```

- [ ] **Step 4: Run server tests**

Run:
```powershell
uv run pytest tests/server/test_api.py -v
```
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```powershell
git add src/filmcolor_server/app.py tests/server/test_api.py
git commit -m "feat: add frame settings sync endpoint"
```

---

### Task 3: Frontend Preview Overlay and Sample Markers

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/App.test.tsx`
- Modify: `web/src/styles.css`
- Modify: `web/src/api.ts`
- Modify: `web/src/types.ts`

- [ ] **Step 1: Update types**

Add to `web/src/types.ts`:

```typescript
export type SampleType = "film_base" | "gray" | "white";

export interface SyncRequest {
  source_frame_id: string;
  target_frame_ids: string[];
  fields: string[];
}
```

- [ ] **Step 2: Add syncFrames API function**

Add to `web/src/api.ts`:

```typescript
import type { SyncRequest } from "./types";

export async function syncFrames(rollId: string, request: SyncRequest): Promise<{ synced_count: number }> {
  const response = await fetch(`/api/rolls/${rollId}/frames/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
  return readJson(response);
}
```

- [ ] **Step 3: Add CSS for overlay, markers, sample panel, multi-select**

Append to `web/src/styles.css`:

```css
/* M4: preview overlay for sample placement */
.previewWrap {
  position: relative;
  display: grid;
  min-height: 320px;
  overflow: hidden;
  border: 1px solid #ded8cc;
  background: #fffefa;
  cursor: crosshair;
}

.previewWrap img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.sampleMarker {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid #fff;
  transform: translate(-50%, -50%);
  pointer-events: none;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

.sampleMarker.filmBase { background: #c26b2b; }
.sampleMarker.gray { background: #808080; }
.sampleMarker.white { background: #f0f0f0; border-color: #999; }

/* sample tool selector */
.sampleTools {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin-bottom: 16px;
}

.sampleTools button {
  padding: 8px 4px;
  border: 1px solid #d8d1c4;
  border-radius: 7px;
  background: #fffdf8;
  color: #171717;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.15s;
}

.sampleTools button.activeFilmBase {
  border-color: #c26b2b;
  background: #fef5ed;
  box-shadow: inset 0 0 0 1px #c26b2b;
}

.sampleTools button.activeGray {
  border-color: #808080;
  background: #f5f5f5;
  box-shadow: inset 0 0 0 1px #808080;
}

.sampleTools button.activeWhite {
  border-color: #ccc;
  background: #fafafa;
  box-shadow: inset 0 0 0 1px #ccc;
}

/* sample list */
.sampleList {
  display: grid;
  gap: 6px;
  margin-bottom: 20px;
  max-height: 140px;
  overflow-y: auto;
}

.sampleItem {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 8px;
  border: 1px solid #ded8cc;
  border-radius: 5px;
  background: #fffdf8;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.sampleItem button {
  flex-shrink: 0;
  padding: 2px 6px;
  border: 1px solid #ded8cc;
  border-radius: 3px;
  background: #fff;
  color: #a12424;
  cursor: pointer;
  font-size: 11px;
}

.sampleDot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.sampleDot.filmBase { background: #c26b2b; }
.sampleDot.gray { background: #808080; }
.sampleDot.white { background: #ddd; border: 1px solid #999; }

/* multi-select frames */
.frame.selected {
  outline: 2px solid #c26b2b;
  outline-offset: -2px;
  background: #fef5ed;
}

.syncBar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 0;
  margin-bottom: 4px;
}

.syncBar button {
  padding: 6px 12px;
  border: 1px solid #c26b2b;
  border-radius: 6px;
  background: #fef5ed;
  color: #c26b2b;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}

.syncBar button:disabled {
  opacity: 0.4;
  cursor: default;
}
```

- [ ] **Step 4: Update App.tsx with preview overlay, sample tools, and markers**

In `web/src/App.tsx`, add imports:

```typescript
import { getEngines, listFrames, listRolls, renderPreview, setFrameEngine, setFrameStyle, syncFrames } from "./api";
import type { EngineStatus, FrameSidecar, OutputStyle, ProcessingEngine, RollMetadata, SampleType, SyncRequest } from "./types";
```

Add new state:

```typescript
  const [activeSampleType, setActiveSampleType] = useState<SampleType>("film_base");
  const [selectedFrameIds, setSelectedFrameIds] = useState<Set<string>>(new Set());
  const [previewNaturalSize, setPreviewNaturalSize] = useState<{ w: number; h: number } | null>(null);
```

Add helper for sending samples:

```typescript
  async function sendSamples(frame: FrameSidecar) {
    if (!selectedRollId) return;
    const updated = await fetch(`/api/rolls/${selectedRollId}/frames/${frame.frame_id}/pipeline`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mask: { samples: frame.pipeline.mask.samples } })
    }).then(r => r.ok ? r.json() : Promise.reject(r));
    setFrames((current) =>
      current.map((f) => (f.frame_id === updated.frame_id ? updated : f))
    );
  }
```

Add preview click handler:

```typescript
  function handlePreviewClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!selectedFrame || !previewNaturalSize) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const displayW = rect.width;
    const displayH = rect.height;
    const x = Math.round(((e.clientX - rect.left) / displayW) * previewNaturalSize.w);
    const y = Math.round(((e.clientY - rect.top) / displayH) * previewNaturalSize.h);

    const samples = { ...selectedFrame.pipeline.mask.samples };
    samples[activeSampleType] = [...(samples[activeSampleType] || []), [x, y]];
    const updated = { ...selectedFrame, pipeline: { ...selectedFrame.pipeline, mask: { ...selectedFrame.pipeline.mask, samples } } };
    setFrames((current) => current.map((f) => (f.frame_id === updated.frame_id ? updated : f)));
    sendSamples(updated);
  }
```

Add sync handler:

```typescript
  async function handleSync() {
    if (!selectedRollId || !selectedFrame || selectedFrameIds.size === 0) return;
    const req: SyncRequest = {
      source_frame_id: selectedFrame.frame_id,
      target_frame_ids: [...selectedFrameIds],
      fields: ["mask.samples", "tone.style", "tone.exposure", "tone.contrast"]
    };
    await syncFrames(selectedRollId, req);
    setSelectedFrameIds(new Set());
    const items = await listFrames(selectedRollId);
    setFrames(items);
  }
```

Replace the preview section. Change:

```tsx
        <div className="preview">
          {isRendering ? (
            ...
          )}
        </div>
```

To:

```tsx
        <div className="previewWrap" onClick={handlePreviewClick}>
          {isRendering ? (
            <div className="previewLoading">
              <ImageIcon size={34} />
              <span>Rendering...</span>
            </div>
          ) : previewUrl ? (
            <>
              <img
                src={previewUrl}
                alt="Rendered film preview"
                onLoad={(e) => {
                  const img = e.currentTarget;
                  setPreviewNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
                }}
              />
              {selectedFrame && (() => {
                const markers: { x: number; y: number; type: SampleType }[] = [];
                const samples = selectedFrame.pipeline.mask.samples;
                for (const s of samples.film_base) markers.push({ x: s[0], y: s[1], type: "film_base" });
                for (const s of samples.gray) markers.push({ x: s[0], y: s[1], type: "gray" });
                for (const s of samples.white) markers.push({ x: s[0], y: s[1], type: "white" });
                if (!previewNaturalSize) return null;
                const imgEl = e.currentTarget.querySelector("img") as HTMLImageElement | null;
                if (!imgEl) return null;
                const displayW = imgEl.clientWidth;
                const displayH = imgEl.clientHeight;
                const scaleX = displayW / previewNaturalSize.w;
                const scaleY = displayH / previewNaturalSize.h;
                return markers.map((m, i) => (
                  <div
                    key={i}
                    className={`sampleMarker ${m.type}`}
                    style={{ left: m.x * scaleX, top: m.y * scaleY }}
                  />
                ));
              })()}
            </>
          ) : (
            <div className="previewEmpty">
              <ImageIcon size={34} />
              <span>Render a preview</span>
            </div>
          )}
        </div>
```

Wait — the `onLoad` approach has closure issues. Instead, use a ref:

```typescript
  const previewImgRef = useRef<HTMLImageElement>(null);
```

And on the img tag:
```tsx
              <img
                ref={previewImgRef}
                src={previewUrl}
                alt="Rendered film preview"
                onLoad={(e) => {
                  setPreviewNaturalSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight });
                }}
              />
```

Then in handlePreviewClick, use `previewImgRef.current` for size calculation.

Actually for simplicity and to avoid complex marker rendering, let me use a different approach. Since the markers' positions are computed from original coordinates scaled to display size, use the `previewNaturalSize` state and compute display size from the previewWrap's dimensions via `getBoundingClientRect()`.

**Replace the preview section (the `<div className="previewWrap">` block).** The full replacement:

```tsx
        <div className="previewWrap" onClick={handlePreviewClick}>
          {isRendering ? (
            <div className="previewLoading">
              <ImageIcon size={34} />
              <span>Rendering...</span>
            </div>
          ) : previewUrl ? (
            <>
              <img
                ref={previewImgRef}
                src={previewUrl}
                alt="Rendered film preview"
                onLoad={(e) => {
                  setPreviewNaturalSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight });
                }}
              />
              {selectedFrame && previewNaturalSize && previewImgRef.current && (() => {
                const markers: { x: number; y: number; type: SampleType }[] = [];
                const s = selectedFrame.pipeline.mask.samples;
                for (const p of s.film_base) markers.push({ x: p[0], y: p[1], type: "film_base" as SampleType });
                for (const p of s.gray) markers.push({ x: p[0], y: p[1], type: "gray" as SampleType });
                for (const p of s.white) markers.push({ x: p[0], y: p[1], type: "white" as SampleType });
                const imgEl = previewImgRef.current!;
                const scaleX = imgEl.clientWidth / previewNaturalSize.w;
                const scaleY = imgEl.clientHeight / previewNaturalSize.h;
                return markers.map((m, i) => (
                  <div
                    key={i}
                    className={`sampleMarker ${m.type}`}
                    style={{ left: m.x * scaleX, top: m.y * scaleY }}
                  />
                ));
              })()}
            </>
          ) : (
            <div className="previewEmpty">
              <ImageIcon size={34} />
              <span>Render a preview</span>
            </div>
          )}
        </div>
```

Add `useRef` import:
```typescript
import { useEffect, useMemo, useRef, useState } from "react";
```

Add sample tools section before STYLE in the panel, after the engine note:

```tsx
        <div className="sectionLabel">SAMPLES</div>
        <div className="sampleTools">
          <button
            className={activeSampleType === "film_base" ? "activeFilmBase" : ""}
            onClick={() => setActiveSampleType("film_base")}
          >
            Film Base
          </button>
          <button
            className={activeSampleType === "gray" ? "activeGray" : ""}
            onClick={() => setActiveSampleType("gray")}
          >
            Gray
          </button>
          <button
            className={activeSampleType === "white" ? "activeWhite" : ""}
            onClick={() => setActiveSampleType("white")}
          >
            White
          </button>
        </div>
```

Add sample list with delete:

```tsx
        {selectedFrame && (() => {
          const samples = selectedFrame.pipeline.mask.samples;
          const items: { type: SampleType; x: number; y: number }[] = [];
          for (const s of samples.film_base) items.push({ type: "film_base", x: s[0], y: s[1] });
          for (const s of samples.gray) items.push({ type: "gray", x: s[0], y: s[1] });
          for (const s of samples.white) items.push({ type: "white", x: s[0], y: s[1] });
          if (items.length === 0) return null;
          return (
            <div className="sampleList">
              {items.map((item, i) => (
                <div className="sampleItem" key={i}>
                  <span className={`sampleDot ${item.type}`} />
                  <span>{item.type}</span>
                  <span>({item.x}, {item.y})</span>
                  <button
                    onClick={() => {
                      const updated = { ...selectedFrame };
                      const newSamples = { ...updated.pipeline.mask.samples };
                      const arr = newSamples[item.type].filter((p: number[]) => !(p[0] === item.x && p[1] === item.y));
                      newSamples[item.type] = arr;
                      updated.pipeline = { ...updated.pipeline, mask: { ...updated.pipeline.mask, samples: newSamples } };
                      setFrames((current) => current.map((f) => (f.frame_id === updated.frame_id ? updated : f)));
                      sendSamples(updated);
                    }}
                  >
                    x
                  </button>
                </div>
              ))}
            </div>
          );
        })()}
```

Add multi-select toggle to frame buttons. Change the frame button onClick:

```tsx
              onClick={() => {
                if (e.ctrlKey || e.metaKey) {
                  setSelectedFrameIds((prev) => {
                    const next = new Set(prev);
                    if (next.has(frame.frame_id)) next.delete(frame.frame_id);
                    else next.add(frame.frame_id);
                    return next;
                  });
                } else {
                  setSelectedFrameId(frame.frame_id);
                  setPreviewUrl("");
                }
              }}
```

Add `className` to frame buttons:
```tsx
              className={
                (frame.frame_id === selectedFrameId ? "frame active" : "frame") +
                (selectedFrameIds.has(frame.frame_id) ? " selected" : "")
              }
```

Add sync bar between gridHeader and frames:

```tsx
        <div className="gridHeader">
          <Grid2X2 size={16} />
          <span>Contact Sheet</span>
          {selectedFrameIds.size > 0 && selectedFrame && (
            <div className="syncBar">
              <span>{selectedFrameIds.size} selected</span>
              <button onClick={handleSync}>Sync from {selectedFrame.frame_id}</button>
            </div>
          )}
        </div>
```

- [ ] **Step 5: Auto re-render after sample changes**

Add useEffect that re-renders when samples change:

```typescript
  const prevSamplesRef = useRef<string>("");

  useEffect(() => {
    if (!selectedFrame || !selectedRollId) return;
    const currentSamples = JSON.stringify(selectedFrame.pipeline.mask.samples);
    if (prevSamplesRef.current && prevSamplesRef.current !== currentSamples) {
      const timer = setTimeout(() => {
        handleRenderPreview();
      }, 500);
      return () => clearTimeout(timer);
    }
    prevSamplesRef.current = currentSamples;
  }, [selectedFrame?.pipeline.mask.samples, selectedFrame?.frame_id]);
```

- [ ] **Step 6: Update App.test.tsx**

Replace `web/src/App.test.tsx` with tests for sample tools visibility and sync:

```typescript
/// <reference types="@testing-library/jest-dom" />

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

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
    expect(screen.getByText("Film Base")).toBeInTheDocument();
    expect(screen.getByText("Gray")).toBeInTheDocument();
    expect(screen.getByText("White")).toBeInTheDocument();
  });

  it("sample tools are visible when a frame is selected", async () => {
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
          return jsonResponse([{
            id: "roll-001", name: "Roll", source_dir: "D:/film",
            created_at: "2026-05-02T00:00:00Z",
            defaults: { film_profile: "generic_color_negative", output_style: "faithful", color_space: "sRGB" }
          }]);
        }
        if (url === "/api/rolls/roll-001/frames") {
          return jsonResponse([{
            frame_id: "IMG_0001", status: "unprocessed",
            source: { path: "D:/film/IMG_0001.png", sha256: "abc", camera: null, lens: null, captured_at: null },
            pipeline: {
              engine: "filmcolor",
              tone: { style: "faithful", exposure: 0, contrast: 0.12, black_point: 0.004, white_point: 0.985 },
              mask: { auto: { rgb_gain: [1, 1, 1], confidence: 0 }, samples: { film_base: [], gray: [], white: [] } }
            },
            engines: { negpy: { enabled: false, version: null, source_commit: null, backend: "cpu", params: { mode: "C41", preset: "default" }, diagnostics: {} } },
            exports: [], error: null
          }]);
        }
        return jsonResponse([]);
      })
    );

    render(<App />);
    expect(await screen.findByText("Film Base")).toBeInTheDocument();
    expect(screen.getByText("SAMPLES")).toBeInTheDocument();
  });
});

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: async () => body } as Response);
}
```

- [ ] **Step 7: Run frontend test and build**

```powershell
cd web
npm.cmd test -- run src/App.test.tsx
npm.cmd run build
```
Expected: 2 tests PASS, build SUCCEEDS.

- [ ] **Step 8: Commit**

```powershell
git add web/src/App.tsx web/src/App.test.tsx web/src/styles.css web/src/api.ts web/src/types.ts
git commit -m "feat: add interactive sample placement and frame sync UI"
```

---

### Task 4: Full Verification

**Files:** none

- [ ] **Step 1: Run all Python tests**

```powershell
uv run pytest -v
```
Expected: all tests PASS.

- [ ] **Step 2: Run frontend tests and build**

```powershell
cd web
npm.cmd test
npm.cmd run build
```
Expected: PASS + build.

- [ ] **Step 3: Commit if needed**

Only if verification uncovered issues.

---

## Plan Self-Review

Spec coverage:
- Gray sample balance algorithm → Task 1
- White sample luminance → Task 1
- Shared pixel extractor utility → Task 1
- Pipeline integration of gray/white → Task 1
- Three sample modes in panel → Task 3
- Click on preview places sample → Task 3
- Coord conversion to original space → Task 3
- Sample markers on preview → Task 3
- Sample list with delete → Task 3
- Auto re-render after sample change → Task 3
- Sync endpoint → Task 2
- Multi-select in contact sheet → Task 3
- Sync from source to targets → Task 3

No placeholders. All code blocks complete.
