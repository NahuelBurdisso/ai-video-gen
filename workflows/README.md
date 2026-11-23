# ComfyUI Workflows for Wan2.2

## How to Create Workflows

Workflow JSONs must be built interactively in ComfyUI after first boot:

### Text-to-Video (wan22-t2v.json)

1. Open ComfyUI at http://localhost:8188
2. Add nodes in this order:
   - `UnetLoaderGGUF` → load `wan2.2-t2v-14B-Q4_K_M.gguf`
   - `DualCLIPLoaderGGUF` or `CLIPLoaderGGUF` → load `umt5-xxl-Q4.gguf`
   - `VAELoader` → load `wan2.2-vae.safetensors`
   - `CLIPTextEncode` → your prompt
   - `WanVideoSampler` (from WanVideoWrapper) → 480x832, 81 frames, CFG 6.0
   - `VAEDecode` (use tiled for >480p)
   - `VHS_VideoCombine` → output MP4
3. Configure memory offloading in WanVideoSampler node settings
4. Save workflow: Menu → Save → `wan22-t2v.json`

### Image-to-Video (wan22-i2v.json)

Same as T2V but add:
- `LoadImage` node → source from /input/
- `CLIPVisionLoader` → load clip-vit-large-patch14.safetensors
- `CLIPVisionEncode` → encode source image
- Use I2V model: `wan2.2-i2v-14B-Q4_K_M.gguf`

### ControlNet (wan22-controlnet.json)

Same as T2V but add:
- `LoadImage` → depth map
- `ControlNetLoader` → wan2.2-controlnet-depth.safetensors
- `ControlNetApply` → connect to sampler

## Memory Settings (Critical for 24GB)

In the WanVideoSampler node, enable:
- T5 CPU offloading after encoding
- Block-level model offloading
- Tiled VAE decoding (for anything above 480p)

Without these, you WILL get OOM errors.

## Exporting Workflows

After building a working workflow:
1. Menu → Save
2. Copy the JSON from ComfyUI's workflow directory to this folder
3. Commit to git for version control
