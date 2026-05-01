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
