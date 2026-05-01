from pathlib import Path

from filmcolor_core.models import FrameSidecar, OutputStyle, RollMetadata
from filmcolor_core.sidecar import (
    read_frame_sidecar,
    read_roll_metadata,
    write_frame_sidecar,
    write_roll_metadata,
)


def test_roll_metadata_round_trips(workspace_tmp_path: Path):
    roll = RollMetadata.create(
        roll_id="2026-05-01-roll-001",
        name="E100 Studio Test",
        source_dir=Path("D:/film/raw/E100-test"),
    )

    path = workspace_tmp_path / "roll.json"
    write_roll_metadata(path, roll)
    loaded = read_roll_metadata(path)

    assert loaded.id == "2026-05-01-roll-001"
    assert loaded.defaults.output_style == OutputStyle.FAITHFUL
    assert loaded.source_dir == "D:/film/raw/E100-test"


def test_frame_sidecar_separates_auto_and_user_values(workspace_tmp_path: Path):
    sidecar = FrameSidecar.create(
        frame_id="IMG_0001",
        source_path=Path("D:/film/raw/E100-test/IMG_0001.CR3"),
        sha256="abc123",
    )
    sidecar.pipeline.mask.auto.rgb_gain = [1.08, 0.97, 0.91]
    sidecar.pipeline.mask.auto.confidence = 0.82
    sidecar.pipeline.mask.samples.film_base = [[120, 840], [134, 842]]

    path = workspace_tmp_path / "IMG_0001.xmp.json"
    write_frame_sidecar(path, sidecar)
    loaded = read_frame_sidecar(path)

    assert loaded.frame_id == "IMG_0001"
    assert loaded.pipeline.mask.auto.rgb_gain == [1.08, 0.97, 0.91]
    assert loaded.pipeline.mask.samples.film_base == [[120, 840], [134, 842]]
