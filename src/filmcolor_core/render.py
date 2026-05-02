from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from filmcolor_core.models import PipelineSettings, ProcessingEngine
from filmcolor_core.negpy_adapter import render_negpy_preview
from filmcolor_core.pipeline import render_pipeline_array
from filmcolor_core.raw import decode_to_linear_rgb


def render_preview_file(
    source_path: Path,
    output_path: Path,
    settings: PipelineSettings,
    max_size: int = 1600,
) -> dict[str, Any]:
    if settings.engine == ProcessingEngine.NEGPY:
        return render_negpy_preview(source_path, output_path, settings, max_size=max_size)

    decoded = decode_to_linear_rgb(source_path)
    rendered, diagnostics = render_pipeline_array(decoded.data, settings, max_size=max_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rendered).save(output_path, quality=90)
    return diagnostics
