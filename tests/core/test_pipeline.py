from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from filmcolor_core import __version__
from filmcolor_core.models import OutputStyle, PipelineSettings
from filmcolor_core.pipeline import (
    _sample_pixels,
    apply_output_style,
    compute_gray_balance,
    compute_white_reference,
    estimate_mask_gain,
    invert_linear,
    normalize_black_white,
    render_pipeline_array,
)


def test_core_package_imports():
    assert __version__ == "0.1.0"


def test_normalize_black_white_clips_to_unit_range():
    image = np.array([[[0.0, 0.5, 1.0], [1.5, -0.5, 0.25]]], dtype=np.float32)

    result = normalize_black_white(image, black_point=0.0, white_point=1.0)

    assert result.min() == 0.0
    assert result.max() == 1.0


def test_invert_linear_keeps_unit_range():
    image = np.array([[[0.1, 0.25, 0.9]]], dtype=np.float32)

    result = invert_linear(image)

    np.testing.assert_allclose(
        result,
        np.array([[[0.9, 0.75, 0.1]]], dtype=np.float32),
        atol=1e-6,
    )


def test_estimate_mask_gain_uses_samples_when_present():
    image = np.ones((4, 4, 3), dtype=np.float32)
    image[1, 1] = [0.5, 1.0, 2.0]

    estimate = estimate_mask_gain(image, film_base_samples=[[1, 1]])

    np.testing.assert_allclose(estimate.rgb_gain, [2.0, 1.0, 0.5], rtol=1e-5)
    assert estimate.confidence == 1.0


def test_estimate_mask_gain_falls_back_to_gray_world():
    image = np.zeros((2, 2, 3), dtype=np.float32)
    image[:, :] = [0.5, 1.0, 2.0]

    estimate = estimate_mask_gain(image, film_base_samples=[])

    np.testing.assert_allclose(estimate.rgb_gain, [2.0, 1.0, 0.5], rtol=1e-5)
    assert estimate.confidence == 0.55


def test_output_styles_have_different_contrast_strengths():
    ramp = np.linspace(0.2, 0.8, 6, dtype=np.float32).reshape(1, 2, 3)

    faithful = apply_output_style(ramp, OutputStyle.FAITHFUL, exposure=0.0, contrast=0.0)
    share = apply_output_style(ramp, OutputStyle.SHARE, exposure=0.0, contrast=0.0)

    assert share.std() > faithful.std()


def test_render_pipeline_array_returns_uint8_preview():
    image = np.full((8, 8, 3), 0.25, dtype=np.float32)
    settings = PipelineSettings()

    rendered, diagnostics = render_pipeline_array(image, settings, max_size=4)

    assert rendered.dtype == np.uint8
    assert rendered.shape == (4, 4, 3)
    assert diagnostics["mask_confidence"] == 0.55


def test_decode_to_linear_rgb_reads_common_image_fixture(workspace_tmp_path: Path):
    from filmcolor_core.raw import decode_to_linear_rgb

    source = workspace_tmp_path / "capture.png"
    Image.new("RGB", (4, 2), color=(64, 128, 192)).save(source)

    decoded = decode_to_linear_rgb(source)

    assert decoded.data.shape == (2, 4, 3)
    assert decoded.data.dtype == np.float32
    assert decoded.metadata["decoder"] == "pillow"


def test_render_preview_file_dispatches_to_negpy(workspace_tmp_path: Path, monkeypatch):
    from filmcolor_core.models import ProcessingEngine
    from filmcolor_core.render import render_preview_file

    source = workspace_tmp_path / "capture.png"
    output = workspace_tmp_path / "preview.webp"
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source)

    settings = PipelineSettings()
    settings.engine = ProcessingEngine.NEGPY

    def fake_negpy(source_path, output_path, pipeline_settings, max_size):
        assert source_path == source
        assert output_path == output
        assert pipeline_settings is settings
        assert max_size == 5
        Image.new("RGB", (5, 5), color=(128, 128, 128)).save(output_path)
        return {"adapter": "fake-negpy"}

    monkeypatch.setattr("filmcolor_core.render.render_negpy_preview", fake_negpy)

    diagnostics = render_preview_file(source, output, settings, max_size=5)

    assert diagnostics["adapter"] == "fake-negpy"
    assert Image.open(output).size == (5, 5)


def test_render_preview_file_writes_webp(workspace_tmp_path: Path):
    from filmcolor_core.render import render_preview_file

    source = workspace_tmp_path / "capture.png"
    output = workspace_tmp_path / "preview.webp"
    Image.new("RGB", (8, 8), color=(64, 128, 192)).save(source)

    diagnostics = render_preview_file(source, output, PipelineSettings(), max_size=4)

    assert output.exists()
    assert diagnostics["mask_confidence"] == 0.55
    assert Image.open(output).size == (4, 4)


def test_compute_gray_balance_returns_identity_when_no_samples():
    image = np.ones((4, 4, 3), dtype=np.float32) * 0.5
    result = compute_gray_balance(image, [])
    assert result == [1.0, 1.0, 1.0]


def test_compute_gray_balance_neutralizes_gray_pixels():
    image = np.ones((4, 4, 3), dtype=np.float32)
    original = np.array([0.5, 0.25, 1.0], dtype=np.float32)
    image[1, 1] = original  # magenta-ish gray sample

    result = compute_gray_balance(image, [[1, 1]])
    gain = np.array(result, dtype=np.float32)

    # Applying the gain should make the sampled pixel roughly equal R=G=B
    neutralized = original * gain
    assert neutralized[0] == pytest.approx(neutralized[1], abs=0.05)
    assert neutralized[0] == pytest.approx(neutralized[2], abs=0.05)
    assert neutralized[1] == pytest.approx(neutralized[2], abs=0.05)


def test_compute_white_reference_returns_one_when_no_samples():
    image = np.ones((4, 4, 3), dtype=np.float32) * 0.5
    result = compute_white_reference(image, [])
    assert result == 1.0


def test_compute_white_reference_uses_sample_luminance():
    image = np.ones((4, 4, 3), dtype=np.float32) * 0.5
    image[2, 2] = [0.9, 0.88, 0.92]

    result = compute_white_reference(image, [[2, 2]])

    assert result > 0.8


def test_sample_pixels_ignores_out_of_bounds():
    image = np.ones((4, 4, 3), dtype=np.float32)
    result = _sample_pixels(image, [[1, 1], [-1, -1], [99, 99], [2, 2]])

    assert len(result) == 2


def test_render_pipeline_array_includes_sampled_values():
    image = np.ones((4, 4, 3), dtype=np.float32) * 0.3
    image[0, 0] = [0.8, 0.6, 0.4]
    image[2, 2] = [0.1, 0.2, 0.3]

    settings = PipelineSettings()
    settings.mask.samples.film_base = [[0, 0]]
    settings.mask.samples.gray = [[2, 2]]

    _, diagnostics = render_pipeline_array(image, settings, max_size=4)

    assert "sampled_values" in diagnostics
    sv = diagnostics["sampled_values"]
    assert len(sv["film_base"]) == 1
    assert len(sv["gray"]) == 1
    assert len(sv["white"]) == 0
    fb = sv["film_base"][0]
    assert len(fb) == 3
    assert abs(fb[0] - 0.8) < 0.05
