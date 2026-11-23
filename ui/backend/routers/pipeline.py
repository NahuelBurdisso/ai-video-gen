import asyncio
import time
import math
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

from ..services.orchestrator import run_pipeline, get_current_run, is_running, request_cancel
from pipeline.state import PipelineState

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

OUTPUT_DIR = Path("D:/ai-output")


class PlanRequest(BaseModel):
    plan: dict


@router.post("/start")
async def start_pipeline(req: PlanRequest):
    if is_running():
        run = get_current_run()
        return {"error": "Pipeline already running", "title": run["title"] if run else None}

    plan = req.plan

    # Compute total clips for immediate response
    p = plan.get("plan", plan)
    fps = p.get("settings", {}).get("fps", 16)
    fpc = p.get("settings", {}).get("frames_per_clip", 81)
    clip_dur = fpc / fps
    total_clips = sum(math.ceil(s["duration"] / clip_dur) for s in p.get("scenes", []))

    # Fire and forget — orchestrator runs as background task
    asyncio.create_task(run_pipeline(plan))

    return {
        "status": "started",
        "title": p.get("title", "untitled"),
        "total_clips": total_clips,
    }


@router.post("/stop")
async def stop_pipeline():
    if not is_running():
        return {"status": "not_running"}
    request_cancel()
    return {"status": "cancel_requested"}


@router.get("/status")
async def pipeline_status():
    run = get_current_run()
    if not run:
        return {"running": False, "title": None, "error": None}

    result = {
        "running": is_running(),
        "title": run["title"],
        "status": run["status"],
        "error": run.get("error"),
        "started_at": run.get("started_at"),
    }

    # Progress from orchestrator state
    result["progress"] = {
        "completed": run.get("completed", 0),
        "total": run.get("total_clips", 0),
    }

    # Check for final output
    if run["title"]:
        final = OUTPUT_DIR / run["title"] / "final.mp4"
        if final.exists():
            result["output"] = f"/static/output/{run['title']}/final.mp4"

    return result


@router.get("/history")
async def pipeline_history():
    projects = []
    if OUTPUT_DIR.exists():
        for d in sorted(OUTPUT_DIR.iterdir()):
            if d.is_dir():
                final = d / "final.mp4"
                state_file = d / "state.json"
                entry = {"title": d.name, "has_final": final.exists()}
                if state_file.exists():
                    try:
                        state = PipelineState.load(state_file)
                        entry["clips"] = len(state.completed)
                        entry["total"] = state.total_clips
                    except Exception:
                        pass
                projects.append(entry)
    return {"projects": projects}
