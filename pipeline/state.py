import json
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class CompletedClip:
    index: int
    clip_type: str
    file: str
    size_bytes: int
    seed: int


@dataclass
class PipelineState:
    title: str
    yaml_hash: str
    total_clips: int
    completed: list[CompletedClip] = field(default_factory=list)
    current: int = 0

    def is_complete(self, index: int) -> bool:
        return any(c.index == index for c in self.completed)

    def mark_complete(self, clip: CompletedClip):
        self.completed.append(clip)
        self.current = clip.index + 1

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "title": self.title,
            "yaml_hash": self.yaml_hash,
            "total_clips": self.total_clips,
            "completed": [asdict(c) for c in self.completed],
            "current": self.current,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        with open(path, "r") as f:
            data = json.load(f)
        state = cls(
            title=data["title"],
            yaml_hash=data["yaml_hash"],
            total_clips=data["total_clips"],
            current=data.get("current", 0),
        )
        state.completed = [
            CompletedClip(**c) for c in data.get("completed", [])
        ]
        return state

    @classmethod
    def load_or_create(cls, path: Path, title: str, yaml_hash: str, total_clips: int, force: bool = False) -> "PipelineState":
        if path.exists() and not force:
            existing = cls.load(path)
            if existing.yaml_hash != yaml_hash:
                raise ValueError(
                    f"Scene script changed since last run. "
                    f"Use --force to restart from scratch."
                )
            return existing
        return cls(title=title, yaml_hash=yaml_hash, total_clips=total_clips)
