# UX Polish Design

Date: 2026-05-02

## Goal

Address five high-priority usability gaps: import UI, contact sheet thumbnails, sample cursor feedback, editable tone controls, and sync confirmation.

## Scope

### U1: Import UI

- Add an "Import" button in the roll sidebar header area
- Clicking opens the native OS folder picker dialog (via `<input type="file" webkitdirectory>`)
- Frontend sends the selected folder path to `POST /api/rolls/import`
- After import, refresh the roll list and select the new roll
- Show error if the folder is invalid or empty

### U2: Contact Sheet Thumbnails

- When a frame's preview is rendered, reuse the same preview image as a thumbnail in the contact sheet
- Thumbnails appear as small background images on the frame buttons
- Frames without previews show the current text-only style
- Thumbnail generation: after render-preview succeeds, the preview URL is already available at `/api/rolls/{roll_id}/frames/{frame_id}/preview`

### U3: Sample Cursor Feedback

- When hovering the preview area, the cursor indicates the active sample type
- Use CSS `cursor` or a small floating label near the cursor showing the sample type name and color dot
- Simplest approach: different cursor styles per type (crosshair variants) + a fixed indicator in the preview area showing "Placing: Film Base" etc.

### U4: Editable Tone Controls

- Replace the read-only Exposure and Contrast readouts with sliders + number display
- Exposure: range -3.0 to +3.0, step 0.1
- Contrast: range 0.0 to 1.0, step 0.01
- Black point and white point stay read-only (derived values)
- Changes PATCH the pipeline and trigger re-render (debounced 500ms)
- Mask confidence stays read-only (auto-computed)

### U5: Sync Confirmation

- After successful sync, show a brief success message that auto-dismisses
- Show "Synced N frames" as a temporary status (not in the error banner, which is for errors)
- Clears after 3 seconds, or on next user action

## Out of Scope

- Before/after comparison
- Keyboard shortcuts
- Collapsible panel sections
- Right-click marker removal
- "Select All" button

## Files Changed

```
web/src/App.tsx           # U1-U5
web/src/App.test.tsx      # U1, U4, U5 tests
web/src/styles.css        # U1-U4 styles
web/src/api.ts            # U1 (importRoll function)
web/src/types.ts          # no changes needed
src/filmcolor_server/app.py  # no changes (existing import endpoint)
```
