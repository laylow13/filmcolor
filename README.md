# Filmcolor

Filmcolor is a local color negative processing workbench. It keeps original captures unchanged, stores processing decisions in JSON sidecars, and renders previews or exports from reproducible pipeline parameters.

## Development Setup

Install Python dependencies with uv:

```powershell
uv sync --extra dev
```

Install frontend dependencies:

```powershell
Set-Location web
npm.cmd install
Set-Location ..
```

## Run Tests

Python:

```powershell
uv run pytest
```

Frontend:

```powershell
Set-Location web
npm.cmd test
npm.cmd run build
Set-Location ..
```

## Run Locally

Start the API:

```powershell
uv run uvicorn filmcolor_server.app:app --reload --host 127.0.0.1 --port 8000
```

Start the web app:

```powershell
Set-Location web
npm.cmd run dev
Set-Location ..
```

Open the Vite URL shown in the terminal. The frontend proxies `/api` requests to `http://127.0.0.1:8000`.

If Windows permissions block uv's default cache, set a project-local cache for that shell:

```powershell
$env:UV_CACHE_DIR = "$PWD\.tmp\uv-cache"
$env:UV_LINK_MODE = "copy"
```

## MVP Workflow

1. Put sample PNG/JPEG/TIFF or supported RAW files in a local folder.
2. Use `POST /api/rolls/import` with the folder path and a roll name.
3. Open the web app to browse imported rolls and frames.
4. Render a preview for a selected frame.
5. Switch output style between `faithful`, `neutral`, and `share`.
