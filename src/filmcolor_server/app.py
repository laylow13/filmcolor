from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from filmcolor_core.models import FrameSidecar, FrameStatus
from filmcolor_core.negpy_adapter import get_negpy_status
from filmcolor_core.render import render_preview_file
from filmcolor_core.sidecar import write_frame_sidecar
from filmcolor_server.jobs import JobRegistry
from filmcolor_server.storage import Workspace


class ImportRollRequest(BaseModel):
    source_dir: str
    name: str


class PipelinePatchRequest(BaseModel):
    engine: str | None = None
    tone: dict[str, Any] | None = None
    mask: dict[str, Any] | None = None
    inversion: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    engines: dict[str, Any] | None = None

    def pipeline_patch_data(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        data.pop("engines", None)
        return data


SYNCABLE_FIELDS = {"mask.samples", "tone.style", "tone.exposure", "tone.contrast"}


class SyncRequest(BaseModel):
    source_frame_id: str
    target_frame_ids: list[str]
    fields: list[str]


def _copy_nested(src: dict[str, Any], dst: dict[str, Any], dotted: str) -> None:
    keys = dotted.split(".")
    for key in keys[:-1]:
        src = src[key]
        dst = dst[key]
    dst[keys[-1]] = copy.deepcopy(src[keys[-1]])


def create_app(workspace_root: Path | None = None) -> FastAPI:
    app = FastAPI(title="Filmcolor")
    workspace = Workspace(workspace_root or Path.cwd() / ".filmcolor-workspace")
    jobs = JobRegistry()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/rolls/import")
    def import_roll(request: ImportRollRequest):
        try:
            return workspace.import_roll(Path(request.source_dir), request.name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/rolls")
    def list_rolls():
        return workspace.list_rolls()

    @app.get("/api/rolls/{roll_id}")
    def get_roll(roll_id: str):
        return workspace.get_roll(roll_id)

    @app.get("/api/rolls/{roll_id}/frames")
    def list_frames(roll_id: str):
        return workspace.list_frames(roll_id)

    @app.get("/api/engines")
    def get_engines():
        try:
            negpy = get_negpy_status()
        except Exception as exc:
            negpy = {
                "available": False,
                "experimental": True,
                "backend": "cpu",
                "reason": str(exc),
            }
        return {
            "filmcolor": {"available": True},
            "negpy": negpy,
        }

    @app.get("/api/rolls/{roll_id}/frames/{frame_id}")
    def get_frame(roll_id: str, frame_id: str):
        return workspace.get_frame(roll_id, frame_id)

    @app.patch("/api/rolls/{roll_id}/frames/{frame_id}/pipeline")
    def patch_pipeline(roll_id: str, frame_id: str, request: PipelinePatchRequest):
        frame = workspace.update_frame_pipeline(roll_id, frame_id, request.pipeline_patch_data())
        if request.engines:
            frame = workspace.update_frame_engines(roll_id, frame_id, request.engines)
        return frame

    @app.post("/api/rolls/{roll_id}/frames/sync")
    def sync_frames(roll_id: str, request: SyncRequest):
        invalid = [f for f in request.fields if f not in SYNCABLE_FIELDS]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Fields not syncable: {invalid}. Valid fields: {sorted(SYNCABLE_FIELDS)}",
            )

        source = workspace.get_frame(roll_id, request.source_frame_id)
        source_data = source.model_dump(mode="json")

        synced = 0
        for target_id in request.target_frame_ids:
            if target_id == request.source_frame_id:
                continue
            frame = workspace.get_frame(roll_id, target_id)
            frame_data = frame.model_dump(mode="json")
            for field in request.fields:
                _copy_nested(source_data["pipeline"], frame_data["pipeline"], field)
            updated = FrameSidecar.model_validate(frame_data)
            updated.status = FrameStatus.MANUALLY_ADJUSTED
            write_frame_sidecar(workspace._frame_path(roll_id, target_id), updated)
            synced += 1

        return {"synced_count": synced}

    @app.post("/api/rolls/{roll_id}/frames/{frame_id}/render-preview")
    def render_preview(roll_id: str, frame_id: str):
        job = jobs.create("render-preview", message=f"Rendering {frame_id}")
        jobs.set_running(job.id, message=f"Rendering {frame_id}")
        try:
            frame = workspace.get_frame(roll_id, frame_id)
            output_path = workspace.preview_path(roll_id, frame_id)
            diagnostics = render_preview_file(
                Path(frame.source.path),
                output_path,
                frame.pipeline,
                max_size=1600,
            )
            if frame.pipeline.engine == "filmcolor":
                frame.pipeline.mask.auto.confidence = diagnostics.get("mask_confidence", 0.0)
            write_frame_sidecar(workspace._frame_path(roll_id, frame_id), frame)
            jobs.set_succeeded(job.id, message=f"Rendered {frame_id}")
            return {
                "job_id": job.id,
                "status": "succeeded",
                "preview_url": f"/api/rolls/{roll_id}/frames/{frame_id}/preview",
                "diagnostics": diagnostics,
            }
        except Exception as exc:
            frame = workspace.get_frame(roll_id, frame_id)
            if frame.pipeline.engine == "negpy":
                frame.engines.negpy.diagnostics["error"] = str(exc)
                write_frame_sidecar(workspace._frame_path(roll_id, frame_id), frame)
            jobs.set_failed(job.id, str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/rolls/{roll_id}/frames/{frame_id}/preview")
    def get_preview(roll_id: str, frame_id: str):
        path = workspace.preview_path(roll_id, frame_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Preview has not been rendered")
        return FileResponse(path)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        try:
            return jobs.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}") from exc

    return app


app = create_app()
