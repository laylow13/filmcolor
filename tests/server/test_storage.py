from pathlib import Path

from PIL import Image

from filmcolor_core.models import FrameStatus
from filmcolor_server.storage import Workspace


def test_import_roll_creates_roll_and_frame_sidecars(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source / "IMG_0001.png")
    Image.new("RGB", (4, 4), color=(40, 50, 60)).save(source / "IMG_0002.jpg")

    workspace = Workspace(workspace_tmp_path / "workspace")
    roll = workspace.import_roll(source, name="E100 Test")
    frames = workspace.list_frames(roll.id)

    assert roll.name == "E100 Test"
    assert len(frames) == 2
    assert frames[0].status == FrameStatus.UNPROCESSED
    assert (workspace_tmp_path / "workspace" / "rolls" / roll.id / "roll.json").exists()


def test_update_frame_pipeline_marks_manual_adjustment(workspace_tmp_path: Path):
    source = workspace_tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(source / "IMG_0001.png")

    workspace = Workspace(workspace_tmp_path / "workspace")
    roll = workspace.import_roll(source, name="E100 Test")
    frame = workspace.list_frames(roll.id)[0]

    updated = workspace.update_frame_pipeline(
        roll.id,
        frame.frame_id,
        {"tone": {"style": "share", "exposure": 0.5}},
    )

    assert updated.status == FrameStatus.MANUALLY_ADJUSTED
    assert updated.pipeline.tone.style == "share"
    assert updated.pipeline.tone.exposure == 0.5
