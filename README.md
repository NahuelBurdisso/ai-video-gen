# AI Video Gen — Local Text-to-Video & Image-to-Video Pipeline

Local AI video generation using Wan2.2 14B (Q4 GGUF quantized) in ComfyUI, running in Docker with NVIDIA GPU passthrough. RTX 3090 optimized.

---

## Prerequisites

- Windows 11 with NVIDIA driver 535+
- Docker Desktop with WSL2 backend enabled
- NVIDIA Container Toolkit installed inside WSL2
- ~35GB free disk for models
- ~50GB free for Docker image + build cache

---

## Quick Start

```bash
docker compose up --build
```

First run downloads ~30GB of models (20–30 min). Then open [http://localhost:8188](http://localhost:8188).

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SKIP_DOWNLOAD=1` | Skip model download (for testing container without models) |

---

## Folder Structure

| Path | Purpose |
|------|---------|
| `D:/ai-models/` | Model weights (persistent) |
| `D:/ai-output/` | Generated videos |
| `D:/ai-input/` | Source images for image-to-video |

---

## Models Included

| Model | Size |
|-------|------|
| Wan2.2 T2V 14B Q4_K_M | ~8GB |
| Wan2.2 I2V 14B Q4_K_M | ~8GB |
| Wan2.2 VAE | ~300MB |
| UMT5-XXL Q4 text encoder | ~5GB |
| CLIP Vision ViT-L/14 | ~1.7GB |
| RealESRGAN x4plus upscaler | ~67MB |
| ControlNet depth (experimental) | ~2–3GB |

---

## Performance (RTX 3090 24GB)

| Mode | Resolution | Frames | Time | VRAM |
|------|-----------|--------|------|------|
| T2V | 480x832 | 81 (5s) | ~3–5 min | ~20GB |
| T2V | 480x832 | 33 (2s) | ~1–2 min | ~18GB |
| I2V | 480x832 | 81 (5s) | ~3–5 min | ~20GB |
| Upscale | 480→1920 | 81 | ~2–3 min | ~4GB |

> **Note:** 720p is NOT recommended — OOM risk. Generate at 480p and upscale with RealESRGAN.

---

## Usage

1. Open [http://localhost:8188](http://localhost:8188)
2. Build workflows per `workflows/README.md`
3. Generated videos appear in `D:/ai-output/`

---

## Director UI (optional)

`start.sh` also launches a web UI (FastAPI backend + React frontend) where a local Ollama LLM acts as a "director": it turns an idea into a multi-scene plan and drives the pipeline. The default model is `gemma3:27b`; override it with the `OLLAMA_MODEL` environment variable (any Ollama model tag works, e.g. `OLLAMA_MODEL=gemma3:12b ./start.sh`). The system prompt lives in `prompts/director.md`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| OOM errors | Close other GPU apps, reduce frame count, ensure memory offloading is enabled |
| GPU not detected | Verify NVIDIA Container Toolkit in WSL2, check `docker exec ai-video-gen nvidia-smi` |
| Slow download | Models download from HuggingFace; use a VPN if throttled, or download manually to `D:/ai-models/` |
| Missing nodes in ComfyUI | Use ComfyUI-Manager to install/update custom nodes |
