from __future__ import annotations

import numpy as np
from PIL import Image

from filmcolor_core.models import OutputStyle, PipelineSettings

EPSILON = 1e-6
DEFAULT_DENSITY = 0.05
DEFAULT_GAMMA = 2.2
DEFAULT_P_LOW = 0.3
DEFAULT_P_HIGH = 99.7


def _sample_pixels(image: np.ndarray, samples: list[list[int]]) -> list[np.ndarray]:
    """Extract pixel values at sample coordinates, skipping out-of-bounds."""
    height, width = image.shape[:2]
    result: list[np.ndarray] = []
    for x, y in samples:
        if 0 <= x < width and 0 <= y < height:
            result.append(image[y, x])
    return result


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0)))


def to_log_density(image: np.ndarray) -> np.ndarray:
    """Convert linear float32 [0,1] to log-density space."""
    return -np.log10(np.clip(image.astype(np.float64), EPSILON, 1.0))


def find_channel_bounds(
    density: np.ndarray,
    film_base_samples: list[list[int]] | None = None,
    p_low: float = DEFAULT_P_LOW,
    p_high: float = DEFAULT_P_HIGH,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Find per-channel D-min (floors) and D-max (ceils).

    If film_base_samples are provided, D-min is estimated from those pixels.
    Otherwise, percentile-based estimation is used.
    """
    if film_base_samples and len(film_base_samples) > 0:
        sampled = _sample_pixels(density, film_base_samples)
        if sampled:
            floors = np.mean(np.stack(sampled), axis=0)
            ceils = np.array([np.percentile(density[..., c], p_high) for c in range(3)])
            ceils = np.maximum(ceils, floors + 0.01)
            return floors.astype(np.float64), ceils.astype(np.float64), 1.0

    floors = np.array([np.percentile(density[..., c], p_low) for c in range(3)], dtype=np.float64)
    ceils = np.array([np.percentile(density[..., c], p_high) for c in range(3)], dtype=np.float64)
    ceils = np.maximum(ceils, floors + 0.01)
    return floors, ceils, 0.55


def normalize_log_channels(density: np.ndarray, floors: np.ndarray, ceils: np.ndarray) -> np.ndarray:
    """Per-channel independent stretch to [0,1], then invert for negative→positive."""
    norm = np.zeros_like(density, dtype=np.float64)
    for c in range(3):
        denom = max(ceils[c] - floors[c], EPSILON)
        norm[..., c] = np.clip((density[..., c] - floors[c]) / denom, 0.0, 1.0)
    # Invert: dense areas (high D) map to bright (high signal)
    return 1.0 - norm.astype(np.float64)


def apply_sigmoid_curve(
    image: np.ndarray,
    density: float = DEFAULT_DENSITY,
    grade: float = 0.0,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    """Apply sigmoid H&D characteristic curve with density/grade control."""
    pivot = 1.0 - (0.01 + density * 0.2)
    slope = 1.0 + grade * 1.75
    d_max = 3.5
    diff = (image - pivot) * slope
    d_out = d_max * _sigmoid(diff * 4.0)
    transmittance = 10.0 ** (-d_out)
    return np.clip(transmittance ** (1.0 / gamma), 0.0, 1.0).astype(np.float32)


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
    """Post-processing style adjustments after the main pipeline."""
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
    """V2 pipeline: log-density normalization with per-channel stretch and sigmoid curve.

    1. Convert linear RGB to log-density space
    2. Find per-channel D-min/D-max (from film_base samples or percentiles)
    3. Per-channel independent stretch to [0,1], then invert
    4. Apply sigmoid H&D characteristic curve
    5. Apply gray balance from gray samples
    6. Apply output style (faithful/neutral/share)
    """
    img_f64 = image.astype(np.float64)

    # Step 1: Log-density conversion
    D = to_log_density(img_f64)

    # Step 2: Per-channel bounds with film_base sample support
    film_base = settings.mask.samples.film_base if settings.mask.samples.film_base else None
    floors, ceils, confidence = find_channel_bounds(D, film_base)
    settings.mask.auto.confidence = confidence
    settings.mask.auto.rgb_gain = [float(ceils[c] - floors[c]) for c in range(3)]

    # Step 3: Per-channel normalize + invert
    normalized = normalize_log_channels(D, floors, ceils)

    # Step 4: Sigmoid H&D curve
    density = getattr(settings.tone, "density", DEFAULT_DENSITY)
    grade = getattr(settings.tone, "grade", 0.0)
    curved = apply_sigmoid_curve(normalized, density=density, grade=grade)

    # Step 5: Gray balance from samples
    gray_gain = compute_gray_balance(curved, settings.mask.samples.gray)
    if gray_gain != [1.0, 1.0, 1.0]:
        g = np.array(gray_gain, dtype=np.float32).reshape(1, 1, 3)
        curved = np.clip(curved.astype(np.float32) * g, 0.0, 1.0)

    # Step 6: Output style
    styled = apply_output_style(
        curved,
        style=settings.tone.style,
        exposure=settings.tone.exposure,
        contrast=settings.tone.contrast,
    )

    # Resize if needed
    if max_size is not None:
        styled = resize_float_image(styled, max_size=max_size)

    rendered = np.clip(styled * 255.0 + 0.5, 0, 255).astype(np.uint8)

    # Collect sampled pixel values for diagnostics
    sampled_values: dict[str, list[list[float]]] = {}
    for sample_type, samples in [
        ("film_base", settings.mask.samples.film_base),
        ("gray", settings.mask.samples.gray),
        ("white", settings.mask.samples.white),
    ]:
        pixels = _sample_pixels(img_f64, samples)
        sampled_values[sample_type] = [p.tolist() for p in pixels]

    return rendered, {
        "mask_confidence": confidence,
        "sampled_values": sampled_values,
    }


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
