import yaml
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClipTask:
    index: int
    clip_type: str  # "t2v" or "i2v"
    scene_index: int
    prompt: str
    is_transition: bool


@dataclass
class ScenePlan:
    title: str
    settings: dict
    negative_prompt: str
    clips: list[ClipTask]

    @property
    def total_clips(self):
        return len(self.clips)

    @property
    def estimated_seconds(self):
        return self.total_clips * 7 * 60  # ~7 min per clip


def parse_scene_file(yaml_path: str) -> ScenePlan:
    path = Path(yaml_path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    settings = data["settings"]
    fps = settings["fps"]
    frames_per_clip = settings["frames_per_clip"]
    clip_duration = frames_per_clip / fps

    clips = []
    clip_index = 0

    for scene_idx, scene in enumerate(data["scenes"]):
        num_clips = math.ceil(scene["duration"] / clip_duration)
        for i in range(num_clips):
            clip_type = "t2v" if clip_index == 0 else "i2v"
            is_transition = (i == 0 and scene_idx > 0)
            clips.append(ClipTask(
                index=clip_index,
                clip_type=clip_type,
                scene_index=scene_idx,
                prompt=scene["prompt"],
                is_transition=is_transition,
            ))
            clip_index += 1

    return ScenePlan(
        title=data["title"],
        settings=settings,
        negative_prompt=data.get("negative_prompt", ""),
        clips=clips,
    )


def get_yaml_hash(yaml_path: str) -> str:
    import hashlib
    with open(yaml_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
