# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```powershell
# Python: install deps, run tests, single test, lint
uv sync --extra dev
uv run pytest                              # all tests
uv run pytest tests/core/test_pipeline.py::test_name -v  # single test
uv run ruff check src/ tests/

# Frontend: install, test, single test, build
cd web && npm install
npm test                                    # vitest
npm test -- run src/App.test.tsx            # single file
npm run build                               # tsc + vite build

# Run locally (two terminals)
uv run uvicorn filmcolor_server.app:app --reload --host 127.0.0.1 --port 8000
cd web && npm run dev                       # → http://127.0.0.1:5173, proxies /api to :8000

# Optional NegPy engine
git submodule update --init --recursive
uv sync --extra dev --extra negpy
```

**Windows note:** If `uv sync` fails with permissions errors, set `$env:UV_CACHE_DIR = "$PWD\.tmp\uv-cache"` and `$env:UV_LINK_MODE = "copy"`.

## Architecture

Filmcolor is a local color-negative film processing workbench. It has four layers:

### 1. Algorithm Library (`src/filmcolor_core/`)

Standalone Python package with no web dependencies. Owns the image processing pipeline end-to-end.

- **`pipeline.py`** — Core processing: `normalize_black_white` → `invert_linear` → `estimate_mask_gain` → `apply_channel_gain` → `compute_gray_balance` → `compute_white_reference` → `apply_output_style` → `render_pipeline_array`. Also contains `_sample_pixels` helper that extracts pixel values at `[x, y]` coordinates with bounds checking.
- **`models.py`** — Pydantic models for sidecars, pipeline settings, and engine configuration. Key hierarchies: `FrameSidecar` contains `PipelineSettings` (engine, mask samples, tone) + `EngineSettings` (negpy block). `MaskSamples` stores `film_base`, `gray`, `white` as `list[list[int]]`.
- **`render.py`** — `render_preview_file()` dispatches by `PipelineSettings.engine`: Filmcolor path calls `render_pipeline_array()`, NegPy path calls `render_negpy_preview()`.
- **`negpy_adapter.py`** — Only module allowed to import NegPy internals. Public API: `get_negpy_status()` (returns `{available, experimental, backend, commit/reason}`), `render_negpy_preview()`. Uses `threading.Lock` for sys.path manipulation. NegPy is imported lazily via `_import_negpy_modules()` with sys.path temporarily modified.
- **`raw.py`** — `decode_to_linear_rgb()` reads image files into float32 numpy arrays.
- **`sidecar.py`** — JSON read/write helpers for `RollMetadata` and `FrameSidecar` via Pydantic serialization.

### 2. Backend Service (`src/filmcolor_server/`)

FastAPI app with local file-based persistence. No database — everything is JSON files on disk.

- **`app.py`** — All API routes inside `create_app()`. Key endpoints:
  - `POST /api/rolls/import` (path-based), `POST /api/rolls/import-upload` (multipart file upload)
  - `PATCH /api/rolls/{id}/frames/{fid}/pipeline` — deep-merges pipeline settings
  - `POST .../render-preview` — dispatches to core, writes preview.webp, returns diagnostics
  - `GET /api/engines` — Filmcolor + NegPy availability
  - `POST .../frames/sync` — copies `mask.samples`, `tone.*` from source to targets
  - `POST .../export` — full-res TIFF/JPEG export
  - `PATCH /api/rolls/{id}` — rename
- **`storage.py`** — `Workspace` class: import rolls, list/get frames, `update_frame_pipeline()` and `update_frame_engines()` with deep-merge, sidecar persistence. Uses `_deep_merge` for nested dict patching.
- **`jobs.py`** — In-memory job registry (create → running → succeeded/failed).

### 3. Frontend (`web/src/`)

React + TypeScript + Vite + Vitest. Single-page workbench with three-column layout.

- **`App.tsx`** — All UI state and rendering. Three areas: roll sidebar, center (preview + contact sheet), right panel (engine, samples, style, readouts). Sample placement via click on preview overlay with coordinate conversion (display pixels → original image coordinates). Multi-select frames with Ctrl+click for batch sync. Keyboard shortcuts: Space=render, 1/2/3=sample type, Backspace=delete last sample, Ctrl+A=select all.
- **`api.ts`** — Fetch wrappers for all backend endpoints. Returns typed JSON.
- **`types.ts`** — TypeScript interfaces matching Pydantic models. `SampleType = "film_base" | "gray" | "white"`, `ProcessingEngine = "filmcolor" | "negpy"`.
- **`styles.css`** — All styling. Design language: Modern Darkroom (warm white, light gray, near black, amber accents `#c26b2b`). Sample markers are absolutely positioned on the preview overlay; sample tool buttons have type-specific active states.

### 4. Data Flow

Original files are never modified. Processing decisions are stored in JSON sidecars (`rolls/{roll_id}/frames/{frame_id}.xmp.json`). Previews are cached as WebP files. The workspace root defaults to `.filmcolor-workspace/` in the current directory.

**Sample → Render cycle:** User clicks preview → `handlePreviewClick` converts display coords to original image coords → `sendSamples` PATCHes mask.samples → debounced re-render → pipeline reads samples from sidecar → returns new preview + diagnostics (including `sampled_values` per sample point).

## Key Design Rules

- `negpy_adapter.py` is the only module that imports NegPy. All other code calls the stable adapter interface.
- NegPy must be optional. Tests pass without it. `GET /api/engines` reports actual availability.
- Sidecars use `pipeline.engine` to select the processing engine. Filmcolor pipeline settings and NegPy settings are independent blocks.
- Frontend treats engine selection as algorithm choice, not output style.
- Use `.worktrees/` for git worktree isolation (already in `.gitignore`).
- Python 3.13 only (`requires-python = ">=3.13,<3.14"`). uv manages all Python deps.

# 前端闭环测试能力

你具备完整的前端开发闭环能力，无需人工干预即可完成以下循环：

## 能力链

1. **编码** — 直接编辑 HTML/CSS/TSX/JSX/TS/JS 等前端文件
2. **运行** — 在终端启动开发服务器 (npm run dev / vite / next dev 等)
3. **浏览** — 通过集成浏览器打开 localhost 页面
4. **感知** — 读取页面的无障碍快照，获取所有可交互元素的结构化信息
5. **操作** — 点击按钮、输入文本、选择下拉项、切换开关、拖拽元素
6. **验证** — 截图对比、读取页面状态变化、处理弹窗
7. **修复** — 发现问题后直接修改源码
8. **循环** — 刷新页面重新验证，直到功能正常

## 触发条件

当用户要求做以下事情时，自动启用闭环模式：
- "实现某个功能并测试"
- "帮我调 UI"
- "检查页面是否正常"
- 任何涉及前端交互验证的任务

## 行为准则

- 写完代码后**主动**打开浏览器验证，不要等用户提醒
- 测试时覆盖正常路径和异常路径（空输入、边界值等）
- 发现问题立即修复，不要只报告不修
- 每个修复后刷新页面重新验证
- 循环不超过 3 轮，如果 3 轮仍未解决，向用户说明卡点