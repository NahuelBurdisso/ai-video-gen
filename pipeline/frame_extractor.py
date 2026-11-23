import subprocess
from pathlib import Path


def extract_last_frame(video_path: str) -> str:
    """Extract last frame from video, return path to PNG."""
    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    frame_path = video.with_suffix(".last_frame.png")

    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",
        "-i", str(video),
        "-vsync", "vfr",
        "-frames:v", "1",
        str(frame_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    if not frame_path.exists() or frame_path.stat().st_size == 0:
        raise RuntimeError(f"Frame extraction produced empty file: {frame_path}")

    return str(frame_path)


def extract_and_upload(video_path: str, client) -> str:
    """Extract last frame and upload to ComfyUI. Returns remote filename."""
    frame_path = extract_last_frame(video_path)
    try:
        remote_name = client.upload_image(frame_path)
        return remote_name
    finally:
        Path(frame_path).unlink(missing_ok=True)
