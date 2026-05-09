from __future__ import annotations

import numpy as np
from PIL import Image

from filmcolor_core.models import MaskAutoEstimate, OutputStyle, PipelineSettings


def _sample_pixels(image: np.ndarray, samples: list[list[int]]) -> list[np.ndarray]:
    """Extract pixel values at sample coordinates, skipping out-of-bounds."""
    height, width = image.shape[:2]
    result: list[np.ndarray] = []
    for x, y in samples:
        if 0 <= x < width and 0 <= y < height:
            result.append(image[y, x])
    return result


def normalize_black_white(image: np.ndarray, black_point: float, white_point: float) -> np.ndarray:
    denominator = max(white_point - black_point, 1e-6)
    return np.clip((image.astype(np.float32) - black_point) / denominator, 0.0, 1.0)


def invert_linear(image: np.ndarray) -> np.ndarray:
    return np.clip(1.0 - image.astype(np.float32), 0.0, 1.0)


def estimate_mask_gain(
    image: np.ndarray,
    film_base_samples: list[list[int]],
) -> MaskAutoEstimate:
    linear = np.maximum(image.astype(np.float32), 1e-6)
    sampled = _sample_pixels(linear, film_base_samples)
    if sampled:
        base = np.mean(np.stack(sampled), axis=0)
        gain = _neutralizing_gain(base)
        return MaskAutoEstimate(rgb_gain=gain.tolist(), confidence=1.0)

    mean_rgb = linear.reshape(-1, 3).mean(axis=0)
    gain = _neutralizing_gain(mean_rgb)
    return MaskAutoEstimate(rgb_gain=gain.tolist(), confidence=0.55)


def apply_channel_gain(image: np.ndarray, rgb_gain: list[float]) -> np.ndarray:
    gain = np.array(rgb_gain, dtype=np.float32).reshape(1, 1, 3)
    return np.clip(image.astype(np.float32) * gain, 0.0, 1.0)


def compute_gray_balance(image: np.ndarray, gray_samples: list[list[int]]) -> list[float]:
    """Return rgb_gain that neutralizes sampled gray pixels to equal R=G=B."""
    sampled = _sample_pixels(image, gray_samples)
    if not sampled:
        return [1.0, 1.0, 1.0]
    avg = np.mean(np.stack(sampled), axis=0)
    gain = _neutralizing_gain(avg)
    return gain.tolist()


def compute_white_reference(image: np.ndarray, white_samples: list[list[int]]) -> float:
    """Return white_point derived from sampled white pixel luminance."""
    sampled = _sample_pixels(image, white_samples)
    if not sampled:
        return 1.0
    avg = np.mean(np.stack(sampled), axis=0)
    luminance = float(avg[0] * 0.2126 + avg[1] * 0.7152 + avg[2] * 0.0722)
    return min(0.995, max(0.7, luminance))


def apply_output_style(
    image: np.ndarray,
    style: OutputStyle,
    exposure: float,
    contrast: float,
) -> np.ndarray:
    exposed = np.clip(image.astype(np.float32) * (2.0**exposure), 0.0, 1.0)
    if style == OutputStyle.NEUTRAL:
        style_contrast = 0.92 + contrast
        saturation = 0.92
    elif style == OutputStyle.SHARE:
        style_contrast = 1.22 + contrast
        saturation = 1.12
    else:
        style_contrast = 1.02 + contrast
        saturation = 1.0

    contrasted = np.clip((exposed - 0.5) * style_contrast + 0.5, 0.0, 1.0)
    luminance = contrasted @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    saturated = luminance[:, :, None] + (contrasted - luminance[:, :, None]) * saturation
    return np.clip(saturated, 0.0, 1.0)


def render_pipeline_array(
    image: np.ndarray,
    settings: PipelineSettings,
    max_size: int | None = None,
) -> tuple[np.ndarray, dict[str, float]]:
    normalized = normalize_black_white(
        image,
        black_point=settings.tone.black_point,
        white_point=settings.tone.white_point,
    )
    inverted = invert_linear(normalized) if settings.inversion.enabled else normalized
    estimate = estimate_mask_gain(inverted, settings.mask.samples.film_base)
    settings.mask.auto = estimate
    balanced = apply_channel_gain(inverted, estimate.rgb_gain)

    gray_gain = compute_gray_balance(balanced, settings.mask.samples.gray)
    balanced = apply_channel_gain(balanced, gray_gain)

    white_ref = compute_white_reference(balanced, settings.mask.samples.white)
    settings.tone.white_point = white_ref

    styled = apply_output_style(
        balanced,
        style=settings.tone.style,
        exposure=settings.tone.exposure,
        contrast=settings.tone.contrast,
    )
    if max_size is not None:
        styled = resize_float_image(styled, max_size=max_size)
    rendered = np.clip(styled * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return rendered, {"mask_confidence": estimate.confidence}


def resize_float_image(image: np.ndarray, max_size: int) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_size:
        return image
    scale = max_size / float(longest)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    pil = Image.fromarray(np.clip(image * 255.0 + 0.5, 0, 255).astype(np.uint8))
    resized = pil.resize(size, Image.Resampling.LANCZOS)
    return np.asarray(resized).astype(np.float32) / 255.0


def _neutralizing_gain(rgb: np.ndarray) -> np.ndarray:
    safe = np.clip(rgb.astype(np.float32), 1e-6, None)
    target = float(np.mean(safe))
    gain = target / safe
    return gain / float(np.median(gain))
