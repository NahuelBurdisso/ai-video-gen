"""Async orchestrator — bridges LLM plans to pipeline modules with WebSocket events."""

import asyncio
import json
import math
import random
import time
from pathlib import Path

from pipeline.comfyui_client import ComfyUIClient
from pipeline.frame_extractor import extract_and_upload
from pipeline.assembler import validate_clips, concat_clips
from pipeline.state import PipelineState, CompletedClip
from pipeline.scene_planner import ClipTask, ScenePlan

from ..ws.manager import manager

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "pipeline" / "templates"
OUTPUT_BASE = Path("D:/ai-output")

# Global lock — one generation at a time
_lock = asyncio.Lock()
_cancel = asyncio.Event()
_current_run: dict | None = None


def get_current_run() -> dict | None:
    return _current_run


def is_running() -> bool:
    return _lock.locked()


def request_cancel():
    _cancel.set()


def _load_template(name: str) -> dict:
    path = TEMPLATES_DIR / name
    with open(path, "r") as f:
        return json.load(f)


def _fill_template(template: dict, params: dict) -> dict:
    text = json.dumps(template)
    for key, value in params.items():
        placeholder = "{{" + key + "}}"
        if isinstance(value, (int, float, bool)):
            text = text.replace(f'"{placeholder}"', str(value).lower() if isinstance(value, bool) else str(value))
        text = text.replace(placeholder, str(value))
    return json.loads(text)


def _plan_to_clips(plan_data: dict) -> ScenePlan:
    """Convert the LLM's JSON plan to ScenePlan with ClipTasks."""
    p = plan_data.get("plan", plan_data)
    settings = p["settings"]
    fps = settings.get("fps", 16)
    frames_per_clip = settings.get("frames_per_clip", 81)
    clip_duration = frames_per_clip / fps

    clips = []
    clip_index = 0
    for scene_idx, scene in enumerate(p["scenes"]):
        num_clips = math.ceil(scene["duration"] / clip_duration)
        input_image = scene.get("input_image")
        for i in range(num_clips):
            # First clip ever is T2V unless it has an explicit input_image
            if clip_index == 0 and not input_image:
                clip_type = "t2v"
            elif input_image and i == 0:
                clip_type = "i2v"
            else:
                clip_type = "i2v"

            clips.append(ClipTask(
                index=clip_index,
                clip_type=clip_type,
                scene_index=scene_idx,
                prompt=scene["prompt"],
                is_transition=(i == 0 and scene_idx > 0),
            ))
            clip_index += 1

    return ScenePlan(
        title=p["title"],
        settings=settings,
        negative_prompt=p.get("negative_prompt", ""),
        clips=clips,
    )


async def run_pipeline(plan_data: dict) -> None:
    """Run full generation pipeline with WebSocket event broadcasting."""
    global _current_run
    _cancel.clear()

    async with _lock:
        p = plan_data.get("plan", plan_data)
        plan = _plan_to_clips(plan_data)

        output_dir = OUTPUT_BASE / plan.title
        clips_dir = output_dir / "clips"
        state_path = output_dir / "state.json"

        _current_run = {
            "title": plan.title,
            "status": "generating",
            "started_at": time.time(),
            "total_clips": plan.total_clips,
            "completed": 0,
            "error": None,
        }

        await manager.broadcast("pipeline_started", {
            "title": plan.title,
            "total_clips": plan.total_clips,
        })

        try:
            client = await asyncio.to_thread(ComfyUIClient)

            clips_dir.mkdir(parents=True, exist_ok=True)
            t2v_template = _load_template("t2v.json")

            # Check if i2v template exists and is valid
            i2v_path = TEMPLATES_DIR / "i2v.json"
            i2v_template = None
            if i2v_path.exists():
                with open(i2v_path, "r") as f:
                    loaded = json.load(f)
                if "_comment" not in loaded:
                    i2v_template = loaded

            # Build state
            yaml_hash = json.dumps(plan_data, sort_keys=True)
            import hashlib
            hash_val = hashlib.sha256(yaml_hash.encode()).hexdigest()
            state = PipelineState(
                title=plan.title,
                yaml_hash=hash_val,
                total_clips=plan.total_clips,
            )

            # Try resuming from existing state
            if state_path.exists():
                try:
                    existing = PipelineState.load(state_path)
                    if existing.yaml_hash == hash_val:
                        state = existing
                except Exception:
                    pass

            # Save run.json for UI state persistence
            run_path = output_dir / "run.json"
            run_data = {
                "plan": plan_data,
                "status": "generating",
                "started_at": _current_run["started_at"],
                "clips": [],
            }
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(run_path, "w") as f:
                json.dump(run_data, f, indent=2)

            last_frame_remote = None
            scenes = p["scenes"]

            for clip in plan.clips:
                if _cancel.is_set():
                    await manager.broadcast("pipeline_cancelled", {"title": plan.title})
                    _current_run["status"] = "cancelled"
                    return

                if state.is_complete(clip.index):
                    clip_file = clips_dir / f"clip_{clip.index:03d}.mp4"
                    if clip_file.exists() and clip.index < plan.total_clips - 1:
                        last_frame_remote = await asyncio.to_thread(
                            extract_and_upload, str(clip_file), client
                        )
                    _current_run["completed"] = clip.index + 1
                    continue

                seed = random.randint(0, 2**32) if plan.settings.get("seed", -1) == -1 else plan.settings["seed"]

                await manager.broadcast("clip_started", {
                    "index": clip.index,
                    "type": clip.clip_type,
                    "scene": clip.scene_index,
                    "prompt": clip.prompt[:100],
                })

                params = {
                    "prompt": clip.prompt,
                    "negative_prompt": plan.negative_prompt,
                    "width": plan.settings["resolution"][0],
                    "height": plan.settings["resolution"][1],
                    "num_frames": plan.settings.get("frames_per_clip", 81),
                    "steps": plan.settings.get("steps", 15),
                    "cfg": plan.settings.get("cfg", 6.0),
                    "shift": plan.settings.get("shift", 5.0),
                    "seed": seed,
                    "filename_prefix": f"{plan.title}_clip_{clip.index:03d}",
                }

                # Handle explicit input_image from scene
                scene = scenes[clip.scene_index]
                explicit_image = scene.get("input_image")

                if clip.clip_type == "t2v":
                    workflow = _fill_template(t2v_template, params)
                elif clip.clip_type == "i2v" and i2v_template:
                    if explicit_image:
                        # Upload user-provided image
                        img_path = Path("D:/ai-input") / explicit_image
                        params["input_image"] = await asyncio.to_thread(
                            client.upload_image, str(img_path)
                        )
                    elif last_frame_remote:
                        params["input_image"] = last_frame_remote
                    else:
                        # Fallback to T2V if no image available
                        workflow = _fill_template(t2v_template, params)
                        # skip the i2v template fill below
                        clip_file = clips_dir / f"clip_{clip.index:03d}.mp4"
                        await _generate_clip(client, workflow, clip, clip_file, seed, state, state_path, plan)
                        if clip_file.exists() and clip.index < plan.total_clips - 1:
                            last_frame_remote = await asyncio.to_thread(
                                extract_and_upload, str(clip_file), client
                            )
                        _current_run["completed"] = clip.index + 1
                        continue
                    workflow = _fill_template(i2v_template, params)
                else:
                    # No i2v template, fallback to t2v
                    workflow = _fill_template(t2v_template, params)

                clip_file = clips_dir / f"clip_{clip.index:03d}.mp4"
                await _generate_clip(client, workflow, clip, clip_file, seed, state, state_path, plan)

                # Extract last frame for next I2V clip
                if clip_file.exists() and clip.index < plan.total_clips - 1:
                    last_frame_remote = await asyncio.to_thread(
                        extract_and_upload, str(clip_file), client
                    )

                _current_run["completed"] = clip.index + 1

            # Assembly
            _current_run["status"] = "assembling"
            await manager.broadcast("assembly_started", {})

            completed_clips = [str(clips_dir / f"clip_{c.index:03d}.mp4") for c in state.completed]
            if completed_clips:
                issues = await asyncio.to_thread(validate_clips, completed_clips)
                if issues:
                    raise RuntimeError(f"Clip validation failed: {issues}")

                final_path = str(output_dir / "final.mp4")
                await asyncio.to_thread(concat_clips, completed_clips, final_path)

                final_url = f"/static/output/{plan.title}/final.mp4"
                total_time = time.time() - _current_run["started_at"]
                _current_run["status"] = "complete"

                await manager.broadcast("pipeline_done", {
                    "final_video_url": final_url,
                    "total_time": round(total_time, 1),
                    "title": plan.title,
                })

                # Update run.json
                run_data["status"] = "complete"
                with open(run_path, "w") as f:
                    json.dump(run_data, f, indent=2)
            else:
                raise RuntimeError("No clips generated")

        except Exception as e:
            _current_run["status"] = "error"
            _current_run["error"] = str(e)
            await manager.broadcast("pipeline_error", {"message": str(e)})
        finally:
            if _current_run and _current_run["status"] not in ("complete", "cancelled"):
                _current_run["status"] = "error"


async def _generate_clip(
    client: ComfyUIClient,
    workflow: dict,
    clip: ClipTask,
    clip_file: Path,
    seed: int,
    state: PipelineState,
    state_path: Path,
    plan: ScenePlan,
):
    """Generate a single clip with retry logic and step-level progress."""
    max_retries = 2
    clip_start = time.time()
    total_steps = plan.settings.get("steps", 15)

    for attempt in range(max_retries + 1):
        try:
            timeout = plan.settings.get("timeout_per_clip", 900)

            outputs = None
            async for event in client.queue_and_track(workflow, timeout=timeout):
                if _cancel.is_set():
                    return

                elapsed = round(time.time() - clip_start, 1)

                if event["type"] == "progress":
                    step = event["step"]
                    max_steps = event["total_steps"]
                    pct = round((step / max_steps) * 100) if max_steps > 0 else 0
                    await manager.broadcast("clip_progress", {
                        "index": clip.index,
                        "elapsed": elapsed,
                        "step": step,
                        "total_steps": max_steps,
                        "pct": pct,
                        "phase": "sampling",
                    })
                elif event["type"] == "node":
                    await manager.broadcast("clip_progress", {
                        "index": clip.index,
                        "elapsed": elapsed,
                        "phase": "processing",
                        "node": event.get("node_id", ""),
                    })
                elif event["type"] == "complete":
                    outputs = event["outputs"]
                    break
                elif event["type"] == "error":
                    raise RuntimeError(f"ComfyUI error: {event['message']}")

            if outputs is None:
                raise RuntimeError(f"No output received for clip {clip.index}")

            # Download phase
            await manager.broadcast("clip_progress", {
                "index": clip.index,
                "elapsed": round(time.time() - clip_start, 1),
                "phase": "downloading",
                "step": total_steps,
                "total_steps": total_steps,
                "pct": 100,
            })

            filename = client.get_output_filename(outputs)
            await asyncio.to_thread(
                client.download_output, filename, str(clip_file)
            )

            elapsed = round(time.time() - clip_start, 1)
            state.mark_complete(CompletedClip(
                index=clip.index,
                clip_type=clip.clip_type,
                file=clip_file.name,
                size_bytes=clip_file.stat().st_size,
                seed=seed,
            ))
            state.save(state_path)

            await manager.broadcast("clip_completed", {
                "index": clip.index,
                "video_url": f"/static/output/{plan.title}/clips/{clip_file.name}",
                "duration": elapsed,
            })
            return

        except Exception as e:
            if attempt < max_retries:
                await manager.broadcast("clip_progress", {
                    "index": clip.index,
                    "retry": attempt + 1,
                    "error": str(e)[:100],
                })
                await asyncio.sleep(10)
            else:
                await manager.broadcast("clip_failed", {
                    "index": clip.index,
                    "error": str(e)[:200],
                })
                raise
