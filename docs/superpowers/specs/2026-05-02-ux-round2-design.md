# UX Polish Round 2 Design

Date: 2026-05-02

## Goal

Second wave of UX improvements: actionable sample list data, intuitive marker removal, panel organization, keyboard efficiency, and batch selection.

## Scope

### U6: Sample RGB Values in List

Replace raw coordinate display `(120, 840)` with the actual RGB values at that sample point. Requires reading pixel data from the rendered preview image. Since we don't have a per-pixel RGB API, store a snapshot of the `MaskAutoEstimate` and sample pixel values alongside the sample list.

Simpler approach: after render, include sampled pixel values in the render diagnostics response. Add `sampled_values: { film_base: [...], gray: [...], white: [...] }` to the diagnostics dict returned by `render_pipeline_array`, keyed by sample coordinate.

Frontend reads these values from the diagnostics and displays them in the sample list.

### U7: Right-Click to Remove Markers

Add `onContextMenu` handler to sample markers on the preview. Right-click on a marker removes that specific sample. Default browser context menu is suppressed via `e.preventDefault()`.

### U8: Collapsible Panel Sections

ENGINE, SAMPLES, and STYLE sections each get a collapsible header. Click the section label to toggle visibility. State persists per session (useState, not saved). Default: all expanded.

A small chevron or +/- indicator on each section label shows collapse state.

### U9: Keyboard Shortcuts

- **Space**: Render preview (when a frame is selected)
- **1**: Switch to Film Base sample mode
- **2**: Switch to Gray sample mode
- **3**: Switch to White sample mode
- **Backspace**: Delete most recently placed sample
- **Ctrl+A / Cmd+A**: Select all frames in contact sheet

All shortcuts use `useEffect` with `keydown` listener, filtered to ignore events when focus is in input fields.

### U10: Select All Button

A small "Select All" / "Deselect All" button next to the sync bar, visible when at least one frame is selected. Click toggles between selecting all frames and clearing selection.

## Out of Scope

- Before/after comparison
- Panel section collapse state persistence across page reloads
- Customizable keyboard shortcuts

## Files Changed

```
web/src/App.tsx         # U6-U10
web/src/App.test.tsx    # U7, U8, U10
web/src/styles.css      # U6, U8
src/filmcolor_core/pipeline.py  # U6: add sampled_values to diagnostics
tests/core/test_pipeline.py     # U6: test sampled_values
```
