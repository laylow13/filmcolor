from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from filmcolor_server.app import create_app


def test_import_roll_and_list_frames(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))

    response = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "E100"})

    assert response.status_code == 200
    roll = response.json()
    frames = client.get(f"/api/rolls/{roll['id']}/frames").json()
    assert len(frames) == 1
    assert frames[0]["frame_id"] == "IMG_0001"


def test_patch_pipeline_and_render_preview(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "E100"}).json()

    patch = client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"tone": {"style": "share", "exposure": 0.25}},
    )
    assert patch.status_code == 200
    assert patch.json()["pipeline"]["tone"]["style"] == "share"

    preview = client.post(f"/api/rolls/{roll['id']}/frames/IMG_0001/render-preview")
    assert preview.status_code == 200
    assert preview.json()["status"] == "succeeded"
    assert preview.json()["diagnostics"]["mask_confidence"] == 0.55


def test_get_engines_reports_negpy_status(workspace_tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "filmcolor_server.app.get_negpy_status",
        lambda: {"available": False, "experimental": True, "backend": "cpu", "reason": "missing"},
    )
    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))

    response = client.get("/api/engines")

    assert response.status_code == 200
    assert response.json()["filmcolor"]["available"] is True
    assert response.json()["negpy"]["available"] is False
    assert response.json()["negpy"]["reason"] == "missing"


def test_patch_endpoint_updates_engine_block(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "NegPy"}).json()

    response = client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"engine": "negpy", "engines": {"negpy": {"enabled": True}}},
    )

    assert response.status_code == 200
    assert response.json()["pipeline"]["engine"] == "negpy"
    assert response.json()["engines"]["negpy"]["enabled"] is True


def test_negpy_preview_failure_persists_diagnostics(workspace_tmp_path: Path, monkeypatch):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source / "IMG_0001.png")

    def fail_render(*args, **kwargs):
        raise RuntimeError("negpy exploded")

    monkeypatch.setattr("filmcolor_core.render.render_negpy_preview", fail_render)
    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source), "name": "NegPy"}).json()
    client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"engine": "negpy", "engines": {"negpy": {"enabled": True}}},
    )

    response = client.post(f"/api/rolls/{roll['id']}/frames/IMG_0001/render-preview")

    assert response.status_code == 500
    frame = client.get(f"/api/rolls/{roll['id']}/frames/IMG_0001").json()
    assert frame["engines"]["negpy"]["diagnostics"]["error"] == "negpy exploded"


def test_engines_endpoint_returns_unavailable_when_status_check_crashes(workspace_tmp_path: Path, monkeypatch):
    def boom():
        raise RuntimeError("status check exploded")

    monkeypatch.setattr("filmcolor_server.app.get_negpy_status", boom)
    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))

    response = client.get("/api/engines")

    assert response.status_code == 200
    assert response.json()["filmcolor"]["available"] is True
    assert response.json()["negpy"]["available"] is False
    assert "status check exploded" in response.json()["negpy"]["reason"]


def test_sync_endpoint_copies_fields_to_target_frames(workspace_tmp_path: Path):
    source_dir = workspace_tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source_dir / "IMG_0001.png")
    Image.new("RGB", (4, 4), color=(40, 50, 60)).save(source_dir / "IMG_0002.png")
    Image.new("RGB", (4, 4), color=(70, 80, 90)).save(source_dir / "IMG_0003.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source_dir), "name": "SyncTest"}).json()

    # Set up source frame with custom samples
    client.patch(
        f"/api/rolls/{roll['id']}/frames/IMG_0001/pipeline",
        json={"mask": {"samples": {"film_base": [[10, 20]], "gray": [[50, 60]]}}, "tone": {"style": "share"}},
    )

    # Sync to IMG_0002 and IMG_0003
    response = client.post(
        f"/api/rolls/{roll['id']}/frames/sync",
        json={
            "source_frame_id": "IMG_0001",
            "target_frame_ids": ["IMG_0002", "IMG_0003"],
            "fields": ["mask.samples", "tone.style"],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["synced_count"] == 2

    frame2 = client.get(f"/api/rolls/{roll['id']}/frames/IMG_0002").json()
    assert frame2["pipeline"]["mask"]["samples"]["film_base"] == [[10, 20]]
    assert frame2["pipeline"]["tone"]["style"] == "share"

    frame3 = client.get(f"/api/rolls/{roll['id']}/frames/IMG_0003").json()
    assert frame3["pipeline"]["tone"]["style"] == "share"


def test_sync_endpoint_rejects_invalid_field(workspace_tmp_path: Path):
    source_dir = workspace_tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source_dir / "IMG_0001.png")
    Image.new("RGB", (4, 4), color=(40, 50, 60)).save(source_dir / "IMG_0002.png")

    client = TestClient(create_app(workspace_root=workspace_tmp_path / "workspace"))
    roll = client.post("/api/rolls/import", json={"source_dir": str(source_dir), "name": "SyncTest"}).json()

    response = client.post(
        f"/api/rolls/{roll['id']}/frames/sync",
        json={
            "source_frame_id": "IMG_0001",
            "target_frame_ids": ["IMG_0002"],
            "fields": ["source.path"],
        },
    )

    assert response.status_code == 422
