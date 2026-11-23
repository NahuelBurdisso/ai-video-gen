#!/usr/bin/env python3
"""Long video generation pipeline - chains T2V and I2V clips."""

import argparse
import json
import random
import sys
import time
from pathlib import Path

from .scene_planner import parse_scene_file, get_yaml_hash
from .comfyui_client import ComfyUIClient
from .frame_extractor import extract_and_upload
from .assembler import validate_clips, concat_clips
from .state import PipelineState, CompletedClip

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_BASE = Path("D:/ai-output")


def load_template(name: str) -> dict:
    path = TEMPLATES_DIR / name
    with open(path, "r") as f:
        return json.load(f)


def fill_template(template: dict, params: dict) -> dict:
    """Replace {{placeholders}} in template with actual values."""
    text = json.dumps(template)
    for key, value in params.items():
        placeholder = "{{" + key + "}}"
        # Handle numeric values (don't quote them)
        if isinstance(value, (int, float, bool)):
            text = text.replace(f'"{placeholder}"', str(value).lower() if isinstance(value, bool) else str(value))
        text = text.replace(placeholder, str(value))
    return json.loads(text)


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def generate(yaml_path: str, dry_run: bool = False, benchmark: bool = False, force: bool = False):
    plan = parse_scene_file(yaml_path)
    yaml_hash = get_yaml_hash(yaml_path)

    output_dir = OUTPUT_BASE / plan.title
    clips_dir = output_dir / "clips"
    state_path = output_dir / "state.json"

    print(f"\n=== Long Video Pipeline ===")
    print(f"Title: {plan.title}")
    print(f"Scenes: {len(set(c.scene_index for c in plan.clips))} | "
          f"Total clips: {plan.total_clips} | "
          f"Estimated time: ~{format_time(plan.estimated_seconds)}")
    print()

    if dry_run:
        for clip in plan.clips:
            label = f"Scene {clip.scene_index + 1}, Clip {clip.index + 1}"
            trans = " (transition)" if clip.is_transition else ""
            print(f"  [{clip.index + 1}/{plan.total_clips}] {label} ({clip.clip_type}{trans})")
            print(f"    Prompt: {clip.prompt[:60]}...")
        return

    # Connect to ComfyUI
    client = ComfyUIClient()

    # Load or create state
    state = PipelineState.load_or_create(state_path, plan.title, yaml_hash, plan.total_clips, force)

    clips_dir.mkdir(parents=True, exist_ok=True)
    t2v_template = load_template("t2v.json")
    i2v_template = load_template("i2v.json")

    if "_comment" in i2v_template:
        print("WARNING: I2V template is still a placeholder. Only T2V clips will work.")
        print("Follow instructions in pipeline/templates/i2v.json to create it.\n")

    total_start = time.time()
    last_frame_remote = None

    for clip in plan.clips:
        if state.is_complete(clip.index):
            clip_file = clips_dir / f"clip_{clip.index:03d}.mp4"
            if clip_file.exists() and clip.index < plan.total_clips - 1:
                last_frame_remote = extract_and_upload(str(clip_file), client)
            print(f"[{clip.index + 1}/{plan.total_clips}] Already done, skipping.")
            continue

        # Check if I2V is needed but template not ready
        if clip.clip_type == "i2v" and "_comment" in i2v_template:
            print(f"[{clip.index + 1}/{plan.total_clips}] SKIPPED — I2V template not ready.")
            continue

        clip_start = time.time()
        seed = random.randint(0, 2**32) if plan.settings.get("seed", -1) == -1 else plan.settings["seed"]

        label = f"Scene {clip.scene_index + 1}"
        trans = ", transition" if clip.is_transition else ""
        print(f"[{clip.index + 1}/{plan.total_clips}] {label} ({clip.clip_type}{trans})... ", end="", flush=True)

        # Build workflow
        params = {
            "prompt": clip.prompt,
            "negative_prompt": plan.negative_prompt,
            "width": plan.settings["resolution"][0],
            "height": plan.settings["resolution"][1],
            "num_frames": plan.settings["frames_per_clip"],
            "steps": plan.settings["steps"],
            "cfg": plan.settings["cfg"],
            "shift": plan.settings["shift"],
            "seed": seed,
            "filename_prefix": f"{plan.title}_clip_{clip.index:03d}",
        }

        if clip.clip_type == "t2v":
            workflow = fill_template(t2v_template, params)
        else:
            params["input_image"] = last_frame_remote
            workflow = fill_template(i2v_template, params)

        # Generate with retry
        max_retries = 2
        clip_file = clips_dir / f"clip_{clip.index:03d}.mp4"

        for attempt in range(max_retries + 1):
            try:
                prompt_id = client.queue_prompt(workflow)
                outputs = client.wait_for_completion(
                    prompt_id, timeout=plan.settings.get("timeout_per_clip", 900)
                )
                filename = client.get_output_filename(outputs)
                client.download_output(filename, str(clip_file))
                break
            except Exception as e:
                if attempt < max_retries:
                    print(f"retry({attempt + 1})... ", end="", flush=True)
                    time.sleep(10)
                else:
                    print(f"\nFATAL: Clip {clip.index} failed after {max_retries + 1} attempts: {e}")
                    state.save(state_path)
                    raise RuntimeError(f"Clip {clip.index} failed: {e}")

        # Extract last frame for next clip
        if clip.index < plan.total_clips - 1:
            last_frame_remote = extract_and_upload(str(clip_file), client)

        # Mark complete
        elapsed = time.time() - clip_start
        state.mark_complete(CompletedClip(
            index=clip.index,
            clip_type=clip.clip_type,
            file=clip_file.name,
            size_bytes=clip_file.stat().st_size,
            seed=seed,
        ))
        state.save(state_path)
        print(f"done ({format_time(elapsed)})")

    # Assembly
    completed_clips = [str(clips_dir / f"clip_{c.index:03d}.mp4") for c in state.completed]
    if not completed_clips:
        print("\nNo clips generated. Nothing to assemble.")
        return

    print(f"\nValidating clips...", end=" ")
    issues = validate_clips(completed_clips)
    if issues:
        print(f"FAILED!")
        for issue in issues:
            print(f"  - {issue}")
        raise RuntimeError(f"Clip validation failed: {issues}")
    print(f"OK ({len(completed_clips)}/{plan.total_clips} valid)")

    print("Assembling final video...")
    final_path = str(output_dir / "final.mp4")
    concat_clips(completed_clips, final_path)

    total_elapsed = time.time() - total_start
    final_size = Path(final_path).stat().st_size / (1024 * 1024)
    clip_duration = plan.settings["frames_per_clip"] / plan.settings["fps"]
    duration_sec = len(completed_clips) * clip_duration

    print(f"\nDONE Output: {final_path} ({duration_sec:.0f} sec, "
          f"{plan.settings['resolution'][0]}x{plan.settings['resolution'][1]}, "
          f"{plan.settings['fps']}fps, {final_size:.1f}MB)")
    print(f"  Clips: {clips_dir}/")
    print(f"  Total time: {format_time(total_elapsed)}")


def main():
    parser = argparse.ArgumentParser(description="Generate long videos from scene scripts")
    parser.add_argument("scene_file", help="Path to YAML scene script")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without generating")
    parser.add_argument("--benchmark", action="store_true", help="Generate 1 clip and estimate total time")
    parser.add_argument("--force", action="store_true", help="Ignore state file, restart from scratch")
    args = parser.parse_args()

    generate(args.scene_file, dry_run=args.dry_run, benchmark=args.benchmark, force=args.force)


if __name__ == "__main__":
    main()
