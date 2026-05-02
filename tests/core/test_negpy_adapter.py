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
    from filmcolor_core.negpy_adapter import _import_negpy_modules, _negpy_root

    root = _negpy_root()
    if not root.exists():
        monkeypatch.setattr("filmcolor_core.negpy_adapter._negpy_root", lambda: Path("Z:/missing/NegPy"))

    results = []
    errors = []

    def call():
        try:
            results.append(get_negpy_status())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 8
