# Interactive Correction Design

Date: 2026-05-02

## Goal

Add click-to-sample on the preview image and frame-to-frame setting synchronization. Users place film-base, gray, and white sample points directly on the rendered preview, see automatic mask gain recalculated from samples, and propagate settings from a tuned frame to others in the same roll.

## Scope

**In:**
- Three sample modes: film-base, gray, white-point — selectable in the panel
- Click on preview image places a sample of the active mode at the clicked coordinates
- Sample markers rendered as colored dots on the preview overlay
- Sample list in panel: coordinate readout, per-sample delete
- Pipeline: gray and white samples feed into channel gain and white-balance calculation
- Re-render automatically after sample changes
- Sync: apply mask samples + tone style from one frame to selected frames or entire roll
- Frame multi-select in the contact sheet

**Out:**
- NegPy engine sampling (NegPy uses its own pipeline)
- Before/after comparison view
- 100% zoom inspection
- Temperature/tint controls
- Undo/redo history

## Sample Coordinates

Samples are stored as `[x, y]` pixel coordinates in the **original image** coordinate space. When the user clicks on a scaled preview, the frontend converts the click position back to original-image coordinates before sending to the API.

Conversion formula: `original_x = round(click_x * original_width / preview_width)`

## Architecture

### Data Model (already exists)

`MaskSamples` in `models.py` already has `film_base`, `gray`, `white` as `list[list[int]]`. No model changes needed.

### Pipeline Extensions

**1. Gray sample handling**

Gray samples represent neutral-gray regions in the scene. After inversion, the pipeline averages the sampled gray pixels and computes a white-balance correction that neutralizes them (equal R=G=B). This is applied as an additional channel gain after mask correction.

```python
def compute_gray_balance(image: np.ndarray, gray_samples: list[list[int]]) -> list[float]:
    """Return rgb_gain that neutralizes sampled gray pixels."""
    if not gray_samples:
        return [1.0, 1.0, 1.0]
    sampled = _sample_pixels(image, gray_samples)
    if not sampled:
        return [1.0, 1.0, 1.0]
    avg = np.mean(np.stack(sampled), axis=0)
    return _neutralizing_gain(avg).tolist()
```

**2. White sample handling**

White samples represent the brightest neutral reference. They adjust the white_point in tone settings. If samples are present, `white_point` is derived from the sampled pixels' luminance.

**3. Sample pixel extraction utility**

Extract the duplicate coordinate-validation logic from `estimate_mask_gain` into a shared helper:

```python
def _sample_pixels(image: np.ndarray, samples: list[list[int]]) -> list[np.ndarray]:
    height, width = image.shape[:2]
    result = []
    for x, y in samples:
        if 0 <= x < width and 0 <= y < height:
            result.append(image[y, x])
    return result
```

### API

**Sample management through existing PATCH endpoint:**

`PATCH /api/rolls/{roll_id}/frames/{frame_id}/pipeline`

```json
{
  "mask": {
    "samples": {
      "film_base": [[120, 840], [134, 842]],
      "gray": [[500, 600]],
      "white": [[800, 200]]
    }
  }
}
```

The existing `_deep_merge` in storage handles nested sample updates. The frontend manages the sample arrays (add/delete) locally, then sends the full samples object.

**Sync endpoint (new):**

`POST /api/rolls/{roll_id}/frames/sync`

```json
{
  "source_frame_id": "IMG_0001",
  "target_frame_ids": ["IMG_0002", "IMG_0003"],
  "fields": ["mask.samples", "tone.style", "tone.exposure"]
}
```

The source frame's specified fields are copied to each target frame's sidecar. Valid fields: `mask.samples`, `tone.style`, `tone.exposure`, `tone.contrast`.

### Frontend

**Preview overlay:**
- Absolute-positioned `<div>` over the `<img>`, matches image display size
- `onClick` handler converts pixel position to original coordinates
- Sample markers: 12px circles with type-specific colors and 2px stroke

**Sample tool selector:**
- Three buttons in the panel below ENGINE: "Film Base" (amber), "Gray" (gray), "White" (white)
- Active mode highlighted; clicking preview places that type of sample

**Sample list:**
- Below the tool selector: list of placed samples with type icon, coordinates, delete button
- Grouped by type

**Contact sheet multi-select:**
- Ctrl+click / Cmd+click to toggle frame selection
- Selected frames show a highlight border
- "Sync from current" button applies current frame's settings to selected frames

**Auto re-render:**
- After PATCH samples succeeds, automatically trigger render-preview
- Debounce: if user clicks rapidly, only render after 500ms pause

## Sync Fields

| Field | Description |
|-------|-------------|
| `mask.samples` | All sample coordinates (film_base, gray, white) |
| `tone.style` | Output style (faithful/neutral/share) |
| `tone.exposure` | Exposure compensation |
| `tone.contrast` | Contrast adjustment |

Per-frame properties NOT synced (by design): source path, sha256, frame_id, engine selection.

## Testing

- Pipeline tests: gray sample neutralization, white sample luminance calculation
- API tests: sample PATCH round-trip, sync endpoint copies fields correctly
- Frontend tests: sample mode selection, coordinate conversion, sync button behavior
