import numpy as np

from filmcolor_core import __version__
from filmcolor_core.models import OutputStyle, PipelineSettings
from filmcolor_core.pipeline import (
    apply_output_style,
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
