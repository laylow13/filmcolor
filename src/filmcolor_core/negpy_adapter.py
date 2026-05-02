from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from filmcolor_core.models import PipelineSettings


class NegPyUnavailable(RuntimeError):
    """Raised when the experimental NegPy adapter cannot run."""


def get_negpy_status() -> dict[str, Any]:
    root = _negpy_root()
    if not root.exists():
        return {
            "available": False,
            "experimental": True,
            "backend": "cpu",
            "reason": f"NegPy submodule is missing at {root}",
        }

    try:
        _import_negpy_modules(root)
    except Exception as exc:
        return {
            "available": False,
            "experimental": True,
            "backend": "cpu",
            "reason": f"NegPy dependencies or imports are unavailable: {exc}",
        }

    return {
        "available": True,
        "experimental": True,
        "backend": "cpu",
        "commit": _negpy_commit(),
    }


def render_negpy_preview(
    source_path: Path,
    output_path: Path,
    settings: PipelineSettings,
    max_size: int = 1600,
) -> dict[str, Any]:
    del settings

    preview, metrics = _run_negpy_cpu(source_path, max_size)
    preview_u8 = (np.clip(preview, 0.0, 1.0) * 255.0).round().astype(np.uint8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(preview_u8).save(output_path)

    return {
        "adapter": "in_process",
        "backend": "cpu",
        "source_commit": _negpy_commit(),
        **metrics,
    }


def _run_negpy_cpu(source_path: Path, max_size: int) -> tuple[np.ndarray, dict[str, Any]]:
    root = _negpy_root()
    if not root.exists():
        raise NegPyUnavailable(f"NegPy submodule is missing at {root}")

    try:
        modules = _import_negpy_modules(root)
    except Exception as exc:
        raise NegPyUnavailable(f"NegPy dependencies or imports are unavailable: {exc}") from exc

    with Image.open(source_path) as image:
        rgb = image.convert("RGB")
        resized = _resize_for_preview(rgb, max_size)
        source = np.asarray(resized, dtype=np.float32) / 255.0

    processor = modules["ImageProcessor"]()
    workspace_config = modules["WorkspaceConfig"]()
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    render_size_ref = float(max(source.shape[:2]))

    try:
        processed, metrics = processor.run_pipeline(
            source,
            workspace_config,
            source_hash,
            render_size_ref=render_size_ref,
            prefer_gpu=False,
            readback_metrics=False,
        )
    finally:
        cleanup = getattr(processor, "cleanup", None)
        if callable(cleanup):
            cleanup()

    if not isinstance(processed, np.ndarray):
        raise NegPyUnavailable("NegPy CPU render did not return an in-memory ndarray")

    return processed.astype(np.float32, copy=False), dict(metrics or {})


def _import_negpy_modules(root: Path) -> dict[str, Any]:
    root_str = str(root)
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


def _resize_for_preview(image: Image.Image, max_size: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= max_size:
        return image.copy()

    scale = max_size / float(longest)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _negpy_root() -> Path:
    return Path(__file__).resolve().parents[2] / "vendor" / "NegPy"


def _negpy_commit() -> str | None:
    root = _negpy_root()
    if not root.exists():
        return None

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    commit = result.stdout.strip()
    return commit or None
