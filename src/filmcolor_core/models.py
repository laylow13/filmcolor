from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class OutputStyle(StrEnum):
    FAITHFUL = "faithful"
    NEUTRAL = "neutral"
    SHARE = "share"


class ProcessingEngine(StrEnum):
    FILMCOLOR = "filmcolor"
    NEGPY = "negpy"


class FrameStatus(StrEnum):
    UNPROCESSED = "unprocessed"
    PROCESSING = "processing"
    AUTO_PROCESSED = "auto_processed"
    MANUALLY_ADJUSTED = "manually_adjusted"
    EXPORTED = "exported"
    FAILED = "failed"
    MISSING = "missing"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class RollDefaults(BaseModel):
    film_profile: str = "generic_color_negative"
    output_style: OutputStyle = OutputStyle.FAITHFUL
    color_space: str = "sRGB"


class RollMetadata(BaseModel):
    id: str
    name: str
    source_dir: str
    created_at: str
    defaults: RollDefaults = Field(default_factory=RollDefaults)

    @classmethod
    def create(cls, roll_id: str, name: str, source_dir: Path) -> "RollMetadata":
        return cls(
            id=roll_id,
            name=name,
            source_dir=source_dir.as_posix(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class SourceMetadata(BaseModel):
    path: str
    sha256: str
    camera: str | None = None
    lens: str | None = None
    captured_at: str | None = None


class RawSettings(BaseModel):
    white_balance: str = "camera"
    black_level_mode: str = "metadata"


class InversionSettings(BaseModel):
    enabled: bool = True
    method: str = "linear_density"


class MaskAutoEstimate(BaseModel):
    rgb_gain: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    confidence: float = 0.0


class MaskSamples(BaseModel):
    film_base: list[list[int]] = Field(default_factory=list)
    gray: list[list[int]] = Field(default_factory=list)
    white: list[list[int]] = Field(default_factory=list)


class MaskSettings(BaseModel):
    auto: MaskAutoEstimate = Field(default_factory=MaskAutoEstimate)
    samples: MaskSamples = Field(default_factory=MaskSamples)


class ToneSettings(BaseModel):
    style: OutputStyle = OutputStyle.FAITHFUL
    exposure: float = 0.0
    contrast: float = 0.12
    black_point: float = 0.004
    white_point: float = 0.985


class NegPyParams(BaseModel):
    mode: str = "C41"
    preset: str = "default"
    density: float | None = None
    grade: float | None = None
    wb_cyan: float | None = None
    wb_magenta: float | None = None
    wb_yellow: float | None = None


class NegPyEngineSettings(BaseModel):
    enabled: bool = False
    version: str | None = None
    source_commit: str | None = None
    backend: str = "cpu"
    params: NegPyParams = Field(default_factory=NegPyParams)
    diagnostics: dict[str, object] = Field(default_factory=dict)


class EngineSettings(BaseModel):
    negpy: NegPyEngineSettings = Field(default_factory=NegPyEngineSettings)


class PipelineSettings(BaseModel):
    version: str = "0.1.0"
    engine: ProcessingEngine = ProcessingEngine.FILMCOLOR
    raw: RawSettings = Field(default_factory=RawSettings)
    inversion: InversionSettings = Field(default_factory=InversionSettings)
    mask: MaskSettings = Field(default_factory=MaskSettings)
    tone: ToneSettings = Field(default_factory=ToneSettings)


class ExportRecord(BaseModel):
    format: str
    path: str
    created_at: str
    color_space: str


class FrameSidecar(BaseModel):
    frame_id: str
    status: FrameStatus = FrameStatus.UNPROCESSED
    source: SourceMetadata
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    engines: EngineSettings = Field(default_factory=EngineSettings)
    exports: list[ExportRecord] = Field(default_factory=list)
    error: str | None = None

    @classmethod
    def create(cls, frame_id: str, source_path: Path, sha256: str) -> "FrameSidecar":
        return cls(
            frame_id=frame_id,
            source=SourceMetadata(path=source_path.as_posix(), sha256=sha256),
        )


class JobRecord(BaseModel):
    id: str
    kind: str
    status: JobStatus
    message: str = ""
    progress: float = 0.0
