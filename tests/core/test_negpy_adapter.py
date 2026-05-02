import threading
from pathlib import Path

import numpy as np
from PIL import Image

from filmcolor_core.models import PipelineSettings
from filmcolor_core.negpy_adapter import get_negpy_status, render_negpy_preview


def test_get_negpy_status_reports_missing_submodule(monkeypatch):
    monkeypatch.setattr("filmcolor_core.negpy_adapter._negpy_root", lambda: Path("Z:/missing/NegPy"))

    status = get_negpy_status()

    assert status["available"] is False
    assert status["experimental"] is True
    assert status["backend"] == "cpu"
    assert "submodule" in status["reason"].lower()


def test_render_negpy_preview_uses_injected_runner(workspace_tmp_path: Path, monkeypatch):
    source = workspace_tmp_path / "source.png"
    output = workspace_tmp_path / "preview.webp"
    Image.new("RGB", (6, 4), color=(64, 128, 192)).save(source)

    def fake_runner(source_path: Path, max_size: int):
        assert source_path == source
        assert max_size == 3
        return np.ones((3, 3, 3), dtype=np.float32) * 0.5, {"fake": True}

    monkeypatch.setattr("filmcolor_core.negpy_adapter._run_negpy_cpu", fake_runner)
    monkeypatch.setattr("filmcolor_core.negpy_adapter._negpy_commit", lambda: "abc123")

    diagnostics = render_negpy_preview(source, output, PipelineSettings(), max_size=3)

    assert output.exists()
    assert Image.open(output).size == (3, 3)
    assert diagnostics["adapter"] == "in_process"
    assert diagnostics["backend"] == "cpu"
    assert diagnostics["source_commit"] == "abc123"
    assert diagnostics["fake"] is True


def test_get_negpy_status_is_thread_safe(monkeypatch):
    # Always mock the import target so the lock is exercised
    # regardless of whether NegPy is installed.
    import types

    def fake_import(root):
        ws = types.ModuleType("negpy.domain.models")
        ws.WorkspaceConfig = dict
        ip = types.ModuleType("negpy.services.rendering.image_processor")
        ip.ImageProcessor = dict
        return {"WorkspaceConfig": dict, "ImageProcessor": dict}

    monkeypatch.setattr(
        "filmcolor_core.negpy_adapter._import_negpy_modules", fake_import
    )

    results = [None] * 8
    errors = [None] * 8

    def call(i):
        try:
            results[i] = get_negpy_status()
        except Exception as exc:
            errors[i] = exc

    threads = [threading.Thread(target=call, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(e is None for e in errors)
    assert all(r is not None for r in results)
