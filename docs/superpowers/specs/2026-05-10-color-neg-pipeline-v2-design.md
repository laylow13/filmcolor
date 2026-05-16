# Filmcolor Pipeline V2 — Log-Density Normalization Design

Date: 2026-05-10

## Current State (V1)

The V1 pipeline in `pipeline.py::render_pipeline_array`:

```
normalize_black_white → invert_linear (1-img) → estimate_mask_gain → apply_channel_gain → apply_output_style
```

**Problem:** PSNR 3.9 dB vs ground truth on eval dataset. Simple linear inversion + channel gain does not correctly handle real color negative film with variable-density orange mask.

## Root Cause Analysis

1. **Inversion order wrong** — The pipeline inverts first, then applies gain. The orange mask is strongest in the negative (dense areas). Simple inversion followed by gain cannot separate the mask from the image signal.
2. **Linear space inversion** — `1.0 - image` assumes linear relationship between density and exposure, but film has a logarithmic response (Hurter-Driffield curve).
3. **Gray-world auto estimate unusable** — For color negatives with strong orange cast, gray-world assumption produces enormous gain values that over-correct.
4. **No per-channel independent normalization** — All channels share the same black/white points, but in color negatives each channel has different D-min (film base) and D-max values.

## Standard Scientific Pipeline

From NegPy, RawTherapee, Darktable Negadoctor, and film physics literature:

```
1. Convert linear sensor data to log density: D = -log10(clip(signal, epsilon, 1.0))
2. Find per-channel D-min and D-max via percentile analysis or film base sampling
3. Per-channel independent stretch to [0,1]: norm = (D - D_min) / (D_max - D_min)
4. Apply sigmoid-based characteristic curve (H&D) with toe/shoulder
5. Apply output gamma and color corrections
```

Key insight: **The orange mask is removed in step 3** — each channel's independent stretch automatically neutralizes the different D-min values caused by the mask. This is why film base sampling is critical: the D-min is measured from unexposed film border areas.

## V2 Pipeline Design

### New Pipeline Flow

```
1. Preprocess: convert to linear float32 if needed (existing raw.py handles this)
2. Log-density conversion: D = -log10(max(image, 1e-6))
3. Per-channel D-min/D-max detection:
   a. If film_base samples exist: use a weighted percentile of sampled pixels
   b. If no samples: use per-channel low/high percentile (0.1% / 99.9%) — NOT gray-world
4. Per-channel stretch: (D - D_min) / (D_max - D_min), clamped to [0, 1]
5. Apply white-balance correction from gray samples (optional step)
6. Apply sigmoid tone curve with density/grade parameters
7. Apply output gamma 2.2
8. Convert to uint8 for display
```

### Changes Required

**`pipeline.py` — `render_pipeline_array` complete rewrite:**
- Remove: `normalize_black_white`, `invert_linear`, `estimate_mask_gain`, `apply_channel_gain`
- Add: `to_log_density`, `find_channel_bounds`, `normalize_log_channels`, `apply_sigmoid_curve`
- Keep: `apply_output_style` (modified for log space), `resize_float_image`

**`models.py` — Minor additions:**
- Add `DensitySettings` to `ToneSettings`: `density: float = 0.0`, `grade: float = 0.0`
- Add `process_mode: str = "C41"` to `PipelineSettings`

**No changes to:**
- `negpy_adapter.py` (still wraps NegPy)
- `render.py` (dispatch logic unchanged)
- `app.py` (API unchanged)
- `storage.py` (sidecar unchanged)
- Frontend (sample placement still works, re-render still works)
- `MaskSamples` (film_base/gray/white samples unchanged)

### Architecture Impact

**No major architecture change.** The pipeline boundary is `render_pipeline_array()` which takes `(image, settings)` and returns `(rendered_uint8, diagnostics)`. Everything upstream (frontend, API, render dispatch) and downstream (image I/O) stays the same.

### Validation Target

Using `eval_examples/` dataset:
- unproc/001-008: 8 color negative scans
- manul_proc/001-008: 8 manual corrections (ground truth)
- Target: PSNR > 15 dB with film_base samples placed on film borders
- Minimum: PSNR > 10 dB with auto percentile estimation
