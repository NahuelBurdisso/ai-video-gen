import json
import time
import asyncio
import uuid
import requests
import websockets
from pathlib import Path
from typing import AsyncGenerator

COMFYUI_URL = "http://localhost:8188"


class ComfyUIClient:
    def __init__(self, base_url: str = COMFYUI_URL):
        self.base_url = base_url
        self._verify_connection()

    def _verify_connection(self):
        try:
            r = requests.get(f"{self.base_url}/system_stats", timeout=5)
            r.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(
                f"Cannot connect to ComfyUI at {self.base_url}. "
                f"Is the container running? Error: {e}"
            )

    def queue_prompt(self, workflow: dict) -> str:
        payload = {"prompt": workflow}
        r = requests.post(f"{self.base_url}/prompt", json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"ComfyUI error: {data['error']}")
        return data["prompt_id"]

    def wait_for_completion(self, prompt_id: str, timeout: int = 900) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(5)
            r = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
            r.raise_for_status()
            data = r.json()
            if prompt_id not in data:
                continue
            entry = data[prompt_id]
            status = entry.get("status", {}).get("status_str")
            if status == "success":
                time.sleep(2)  # Race condition guard
                return entry.get("outputs", {})
            elif status == "error":
                messages = entry.get("status", {}).get("messages", [])
                error_msg = str(messages[-1] if messages else "Unknown error")
                raise RuntimeError(f"Generation failed: {error_msg}")
        raise TimeoutError(f"Generation timed out after {timeout}s")

    def upload_image(self, filepath: str) -> str:
        path = Path(filepath)
        with open(path, "rb") as f:
            r = requests.post(
                f"{self.base_url}/upload/image",
                files={"image": (path.name, f, "image/png")},
                timeout=30,
            )
        r.raise_for_status()
        data = r.json()
        return data.get("name", path.name)

    def get_output_filename(self, outputs: dict, node_id: str = "10") -> str:
        node_output = outputs.get(node_id, {})
        videos = node_output.get("videos", node_output.get("gifs", []))
        if not videos:
            raise RuntimeError(f"No video output found in node {node_id}")
        return videos[0]["filename"]

    async def queue_and_track(
        self, workflow: dict, timeout: int = 900
    ) -> AsyncGenerator[dict, None]:
        """Queue a prompt and yield progress events via ComfyUI WebSocket.

        Yields dicts like:
          {"type": "progress", "step": 5, "total_steps": 20}
          {"type": "node", "node_id": "3", "node_type": "KSampler"}
          {"type": "complete", "outputs": {...}}
          {"type": "error", "message": "..."}
        """
        client_id = uuid.uuid4().hex[:12]
        ws_url = self.base_url.replace("http://", "ws://") + f"/ws?clientId={client_id}"

        # Queue with client_id so ComfyUI routes WS messages to us
        payload = {"prompt": workflow, "client_id": client_id}
        r = requests.post(f"{self.base_url}/prompt", json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"ComfyUI error: {data['error']}")
        prompt_id = data["prompt_id"]

        start = time.time()
        try:
            async with websockets.connect(ws_url, ping_interval=30, ping_timeout=10) as ws:
                async for raw in ws:
                    if time.time() - start > timeout:
                        raise TimeoutError(f"Generation timed out after {timeout}s")

                    msg = json.loads(raw)
                    msg_type = msg.get("type")

                    if msg_type == "progress":
                        d = msg.get("data", {})
                        yield {
                            "type": "progress",
                            "step": d.get("value", 0),
                            "total_steps": d.get("max", 0),
                        }
                    elif msg_type == "executing":
                        d = msg.get("data", {})
                        if d.get("node") is None and d.get("prompt_id") == prompt_id:
                            # Execution complete — fetch outputs from history
                            await asyncio.sleep(1)  # Race condition guard
                            r2 = requests.get(
                                f"{self.base_url}/history/{prompt_id}", timeout=10
                            )
                            r2.raise_for_status()
                            hist = r2.json()
                            entry = hist.get(prompt_id, {})
                            status = entry.get("status", {}).get("status_str")
                            if status == "error":
                                messages = entry.get("status", {}).get("messages", [])
                                err = str(messages[-1] if messages else "Unknown error")
                                yield {"type": "error", "message": err}
                            else:
                                yield {"type": "complete", "outputs": entry.get("outputs", {})}
                            return
                        else:
                            yield {"type": "node", "node_id": d.get("node", "")}
                    elif msg_type == "execution_error":
                        d = msg.get("data", {})
                        yield {"type": "error", "message": d.get("exception_message", "Unknown error")}
                        return
        except websockets.exceptions.ConnectionClosed:
            raise RuntimeError("ComfyUI WebSocket connection lost during generation")

    def download_output(self, filename: str, dest_path: str):
        url = f"{self.base_url}/view?filename={filename}&type=output"
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        if dest.stat().st_size < 10240:
            raise RuntimeError(f"Downloaded file too small: {dest.stat().st_size} bytes")
