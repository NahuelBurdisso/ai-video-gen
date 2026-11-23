import subprocess
from pathlib import Path


def validate_clips(clip_paths: list[str]) -> list[str]:
    """Validate all clips exist and are valid. Returns list of issues."""
    issues = []
    for path in clip_paths:
        p = Path(path)
        if not p.exists():
            issues.append(f"Missing: {path}")
            continue
        if p.stat().st_size < 10240:
            issues.append(f"Too small ({p.stat().st_size} bytes): {path}")
            continue
        # Probe with ffmpeg
        cmd = ["ffmpeg", "-i", str(p), "-f", "null", "-"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            issues.append(f"Invalid video: {path}")
    return issues


def concat_clips(clip_paths: list[str], output_path: str) -> str:
    """Concatenate clips using ffmpeg concat demuxer. Returns output path."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Write concat list file
    list_file = output.with_suffix(".txt")
    with open(list_file, "w") as f:
        for clip in clip_paths:
            # ffmpeg concat needs forward slashes and escaped quotes
            escaped = str(Path(clip).resolve()).replace("\\", "/")
            f.write(f"file '{escaped}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")

    return str(output)
