# Color Negative Film Conversion Design

Date: 2026-05-01

## Goal

Build a local film-processing platform for freshly developed color negative film captures made with a digital camera. The first version treats camera RAW files as the primary input, performs negative-to-positive inversion, removes the orange film-base mask, supports whole-roll batch processing, and provides a modern web workbench for review, correction, synchronization, and export.

The project should produce repeatable results rather than destructive edits. All automatic estimates, user corrections, output styles, and export settings are stored in sidecar files so every result can be regenerated.

## Product Scope

The first release includes:

- A Python algorithm library for RAW decoding, density-aware negative inversion, orange-mask estimation, tone mapping, and export preparation.
- A FastAPI local backend for roll/session management, background jobs, preview caching, sidecar persistence, and batch export.
- A web frontend for importing a roll, browsing thumbnails, previewing individual frames, sampling film base/gray/white points, editing parameters, syncing settings, and exporting TIFF/JPEG files.
- Three output styles: faithful, neutral, and share.
- Sidecar-based reproducibility for every frame.

The first release does not include:

- Cloud accounts or multi-user workflows.
- Full library/catalog management.
- Machine-learning correction.
- Lightroom or Photoshop plugins.
- Full XMP compatibility.
- Advanced dust removal, automatic perspective correction, or automatic frame detection unless later scoped as separate modules.

## Design Direction

The interface should feel like a modern digital darkroom, not a retro-themed web page.

The main UI uses a Modern Darkroom language: minimal, spacious, precise, and centered on the image. The palette is warm white, light gray, and near black, with restrained amber film-base accents and small lab-red highlights.

The preview and roll areas borrow from a light table: thumbnail grids can resemble contact sheets or film strips, selected frames can show subtle frame boundaries and frame numbers, and the large preview area can use a clean light-table background.

Retro Lab details are limited to identity and status elements: `ROLL` and `FRAME` labels, lab-note-like export records, and small processing-status marks. Avoid large film perforation decorations, heavy vintage typography, dark brown/red darkroom themes, nested dashboard cards, decorative gradients, and marketing-page styling.

## Architecture

The project is split into four layers.

### Algorithm Library: `filmcolor-core`

`filmcolor-core` is a standalone Python package. It owns RAW decoding, linearization, negative inversion, film-base/orange-mask estimation, point sampling, channel balancing, tone mapping, output color conversion, preview rendering, and full-resolution render preparation.

It should not depend on the web frontend. It accepts image paths and pipeline parameters, then returns rendered image data, derived measurements, diagnostics, and metadata. This lets the core be tested independently and reused later by a CLI, desktop app, or plugin.

### Backend Service: `filmcolor-server`

`filmcolor-server` is a local FastAPI service. It owns project state, roll/session indexing, task scheduling, preview and thumbnail caching, sidecar persistence, export jobs, error reporting, and settings.

The backend is the boundary between UI interaction and image processing. It should call `filmcolor-core` instead of embedding algorithm details in API handlers.

### Web Frontend: `filmcolor-web`

`filmcolor-web` is a browser-based local workbench. It supports whole-roll import, thumbnail browsing, single-frame preview, before/after comparison, sample-point placement, parameter editing, parameter synchronization across selected frames, export queue review, and job progress.

The frontend should keep long operations asynchronous and show clear statuses for unprocessed, processing, adjusted, exported, failed, and missing frames.

### Workspace Data

Project data is organized around roll/session folders. Original RAW files are referenced, not modified. The workspace stores roll metadata, frame sidecars, previews, thumbnails, exports, and logs.

Example layout:

```text
workspace/
  rolls/
    2026-05-01-roll-001/
      roll.json
      frames/
        IMG_0001.xmp.json
        IMG_0002.xmp.json
      previews/
        IMG_0001.preview.webp
        IMG_0001.thumb.webp
      exports/
        tiff/
        jpeg/
      logs/
```

## Image Processing Pipeline

The pipeline is designed to be explainable, replayable, and adjustable.

### 1. RAW Read and Linearization

The core reads camera RAW files and produces linear RGB data while preserving dynamic range. It records camera model, lens when available, capture time, black level, white level, white balance source, color matrix data, and RAW decoding settings.

The first implementation should avoid applying camera picture styles or destructive tone curves before negative inversion and mask correction.

### 2. Capture Normalization

The pipeline includes hooks for camera-copying corrections: black/white normalization, exposure compensation, and optional vignetting/flat-field correction. First-version flat-field correction can be manual or disabled by default, but the pipeline should leave a clear interface for it.

### 3. Negative Inversion

Inversion should happen in a linear or density-aware representation rather than by subtracting gamma-encoded values. For color negative film, this step converts the orange-masked negative capture into a positive image while preserving density relationships. Black and white references must be handled around inversion so exposure range does not distort orange-mask estimation.

### 4. Film Base and Orange-Mask Estimation

The default path estimates channel bias and the color negative orange mask automatically from the image. If film borders, unexposed film-base regions, or user-selected film-base samples are available, they take priority.

The frontend allows users to place film-base, gray, and white samples. The algorithm library converts these samples into explicit constraints. Film-base samples are especially important for color negative stock because the orange mask varies by stock, exposure, and capture setup. Automatic estimates include confidence values so the UI can flag frames that need user attention.

### 5. Color Balance and Neutralization

The first version combines color-science methods with visual heuristics. Color-science steps include channel gain, white balance, neutral-axis constraints, and matrix-based color transforms. Heuristic steps include gray-world correction, percentile clipping, and global contrast protection.

Automatic values and user overrides must be stored separately so users can return to the automatic result or inspect what has been manually changed.

### 6. Output Styles

The platform provides three output styles:

- `faithful`: preserves a natural color-negative film character after conversion without forcing a modern digital look.
- `neutral`: produces a lower-contrast, more neutral output that keeps room for later editing.
- `share`: applies stronger automatic contrast, brightness, and saturation for immediate sharing.

The default style is configurable at the roll level.

### 7. Export

Preview rendering uses cached JPEG or WebP assets. Final export supports 16-bit TIFF and high-quality JPEG. Export metadata records algorithm version, pipeline parameter version, input file hash, output color space, and export settings.

## Frontend Interaction Model

The workbench is optimized for whole-roll processing with selective refinement.

### Roll Sidebar

The left area lists imported rolls/sessions with name, date, frame count, processing status, and export status. First release supports local folder import without full catalog management.

### Thumbnail Grid

The central grid displays the roll as a contact-sheet-like set of frames. Each frame shows its status: unprocessed, auto-processed, manually adjusted, exported, failed, or missing. Multi-select enables setting synchronization and batch actions.

### Parameter Panel

The right panel groups controls by purpose:

- Input: exposure, black point, white point, inversion mode.
- Mask: automatic estimate, film-base samples, channel gains.
- Neutral correction: gray samples, white samples, temperature/tint.
- Style: faithful, neutral, share.
- Output: TIFF/JPEG, color space, quality, naming template.

### Preview and Compare View

The large preview supports original capture, inverted intermediate, and current result. It includes before/after comparison, 100% inspection, and click sampling for film base, gray point, and white point. The UI can display sampled RGB values, linear values, and corrected values.

### Batch Workflow

The expected workflow is:

1. Import a folder of RAW captures as one roll.
2. Generate thumbnails and initial low-resolution previews.
3. Auto-process the roll.
4. Pick representative frames and adjust them.
5. Sync selected parameters to selected frames or the whole roll while preserving per-frame exposure differences.
6. Export TIFF and/or JPEG outputs.

## Sidecar Format

Sidecars are JSON for the first version because JSON is readable, diffable, easy to test, and easy for the frontend/backend to share. Future XMP compatibility can be added as an import/export bridge.

`roll.json` stores roll-level defaults and source information:

```json
{
  "id": "2026-05-01-roll-001",
  "name": "E100 Studio Test",
  "source_dir": "D:/film/raw/E100-test",
  "created_at": "2026-05-01T20:30:00+08:00",
  "defaults": {
    "film_profile": "generic_color_negative",
    "output_style": "faithful",
    "color_space": "Display P3"
  }
}
```

Each frame has a sidecar such as `IMG_0001.xmp.json`:

```json
{
  "source": {
    "path": "D:/film/raw/E100-test/IMG_0001.CR3",
    "sha256": "...",
    "camera": "Canon EOS R5",
    "lens": "Macro 100mm",
    "captured_at": "2026-05-01T14:12:00+08:00"
  },
  "pipeline": {
    "version": "0.1.0",
    "raw": {
      "white_balance": "camera",
      "black_level_mode": "metadata"
    },
    "inversion": {
      "enabled": true,
      "method": "linear_density"
    },
    "mask": {
      "auto": {
        "rgb_gain": [1.08, 0.97, 0.91],
        "confidence": 0.82
      },
      "samples": {
        "film_base": [[120, 840], [134, 842]],
        "gray": [],
        "white": []
      }
    },
    "tone": {
      "style": "faithful",
      "exposure": 0.0,
      "contrast": 0.12,
      "black_point": 0.004,
      "white_point": 0.985
    }
  },
  "exports": []
}
```

Design rules:

- Sidecars are the source of truth for processing state.
- Automatic estimates and user overrides are separate.
- Roll defaults and frame parameters are layered.
- Original RAW files are referenced and never modified.
- Sidecars include pipeline and algorithm versions for future migrations.

## Backend API and Jobs

The FastAPI backend exposes project, frame, job, and export endpoints.

Representative API:

```text
POST   /api/rolls/import
GET    /api/rolls
GET    /api/rolls/{roll_id}
GET    /api/rolls/{roll_id}/frames

GET    /api/frames/{frame_id}
PATCH  /api/frames/{frame_id}/pipeline
POST   /api/frames/{frame_id}/render-preview
POST   /api/frames/{frame_id}/sample-point

POST   /api/jobs
GET    /api/jobs/{job_id}
POST   /api/exports
```

Long-running operations use a local task queue. The first version can use an in-process queue or lightweight persistent queue rather than a distributed worker system.

Job states:

```text
queued -> running -> succeeded
                  -> failed
                  -> canceled
```

Queue categories:

- Small tasks: sidecar updates and simple metadata reads.
- Medium tasks: preview rendering and thumbnail generation.
- Large tasks: whole-roll auto-processing and full-resolution batch export.

## Error Handling

The system should continue processing a roll even when individual frames fail.

Expected failure cases:

- RAW decode failure marks a frame as failed and records the exception.
- Low-confidence color-cast estimation still produces a result but flags the frame for sampling.
- Preview cache corruption triggers automatic regeneration.
- Missing source files preserve frame records but show a missing status.
- Export failures record output format, path, and exception details.

Errors should be visible in the UI and persisted in logs or sidecars where appropriate.

## Performance Strategy

Import should generate small thumbnails first, then larger previews on demand. The frontend should load previews near the current viewport rather than the whole roll at once.

Whole-roll auto-processing can estimate parameters from downsampled image data. Final export should re-render from full-resolution RAW data using the stored sidecar parameters.

Preview cache keys include input file hash, algorithm version, and pipeline parameter hash. This prevents stale previews from being reused after parameter or algorithm changes.

## Testing Strategy

### Algorithm Tests

- Verify RAW decode and metadata extraction with small fixtures.
- Verify negative inversion, black/white handling, channel gain, orange-mask compensation, and tone mapping.
- Verify that the same input plus sidecar gives reproducible output.
- Verify confidence behavior for color-cast estimation.

### Backend Tests

- Verify roll and sidecar creation, reading, and updating.
- Verify job state transitions.
- Verify cache invalidation after parameter changes.
- Verify single-frame failures do not stop whole-roll processing.

### Frontend Tests

- Verify roll import states: empty, processing, failed, complete.
- Verify thumbnail grid rendering and multi-select.
- Verify parameter synchronization.
- Verify sample-point interactions update sidecars.
- Verify export queue status display.

## Milestones

### M1: Core Algorithm Loop

RAW input to linear data, negative inversion, basic automatic orange-mask correction, and preview/TIFF/JPEG output. This milestone can be verified through tests or a minimal CLI.

### M2: Roll and Sidecar Management

Create roll/session records, index RAW files, generate sidecars, and cache thumbnails. The backend understands a roll as a coherent batch rather than isolated files.

### M3: Web Workbench MVP

Import a roll, browse thumbnails, inspect one frame, switch output styles, edit basic parameters, and render previews in the browser.

### M4: Interactive Correction

Support film-base, gray-point, and white-point sampling. Allow representative-frame settings to be synchronized to selected frames or the full roll.

### M5: Batch Export and Reproducibility

Support TIFF/JPEG export, export queue status, sidecar-based regeneration, export metadata, and algorithm version tracking.

## Open Decisions

These decisions are intentionally deferred until implementation planning:

- Exact RAW decoding library selection.
- Exact frontend framework.
- Whether preview images use JPEG, WebP, or both.
- Initial supported camera RAW formats.
- Initial fixture images for algorithm tests.
