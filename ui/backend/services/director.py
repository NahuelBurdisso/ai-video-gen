import json
import re
import math
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "director.md"

DEFAULTS = {
    "frames_per_clip": 81,
    "shift": 5.0,
    "seed": -1,
    "fps": 16,
    "timeout_per_clip": 900,
}

MAX_PIXELS = 832 * 480  # Max total pixels (supports both landscape and portrait)


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_plan_json(text: str) -> dict | None:
    """Extract JSON plan from the LLM's response. Returns None if no plan found."""
    # Look for ```json ... ``` blocks (greedy to capture nested braces)
    pattern = r"```json\s*(\{.*\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        # Try bare JSON block (greedy)
        pattern = r'(\{"action"\s*:\s*"generate".*\})\s*$'
        match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        if data.get("action") == "generate" and "plan" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


def validate_and_normalize_plan(plan: dict) -> tuple[dict, list[str]]:
    """Validate plan from the LLM. Returns (normalized_plan, warnings)."""
    warnings = []
    p = plan["plan"]

    # Sanitize title
    title = re.sub(r"[^a-zA-Z0-9_-]", "_", p.get("title", "untitled"))
    p["title"] = title

    # Clamp resolution (supports both landscape [832,480] and portrait [480,832])
    settings = p.get("settings", {})
    res = settings.get("resolution", [832, 480])
    if res[0] * res[1] > MAX_PIXELS:
        warnings.append(f"Resolution {res} exceeds max pixels ({MAX_PIXELS}), clamped to [832, 480]")
        res = [832, 480]
    # Ensure dimensions are valid (both must be > 0 and <= 832)
    if res[0] > 832 or res[1] > 832 or res[0] <= 0 or res[1] <= 0:
        warnings.append(f"Resolution {res} has invalid dimensions, clamped to [832, 480]")
        res = [832, 480]
    settings["resolution"] = res

    # Apply defaults
    for key, default in DEFAULTS.items():
        settings.setdefault(key, default)
    p["settings"] = settings

    # Validate scenes
    if not p.get("scenes"):
        raise ValueError("Plan has no scenes")

    for i, scene in enumerate(p["scenes"]):
        if not scene.get("prompt"):
            raise ValueError(f"Scene {i} has no prompt")
        dur = scene.get("duration", 5)
        if dur <= 0:
            raise ValueError(f"Scene {i} has invalid duration: {dur}")
        # Round up to nearest 5
        scene["duration"] = math.ceil(dur / 5) * 5

        # Validate input_image exists
        img = scene.get("input_image")
        if img:
            img_path = Path("D:/ai-input") / img
            if not img_path.exists():
                raise ValueError(f"Scene {i} references missing image: {img}")

    p.setdefault("negative_prompt", "blurry, low quality, distorted, deformed, bad anatomy, ugly")

    return plan, warnings
