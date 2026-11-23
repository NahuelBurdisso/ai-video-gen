#!/bin/bash
set -e

echo "=== AI Video Gen Container Starting ==="

# Check GPU
echo "GPU Status:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || echo "WARNING: GPU not detected!"

# Model download (skip if SKIP_DOWNLOAD=1)
if [ "${SKIP_DOWNLOAD}" = "1" ]; then
    echo "SKIP_DOWNLOAD=1, skipping model check."
elif [ ! -f "/models/wan2.2/wan2.2-t2v-14B-Q5_K_M.gguf" ] && [ ! -f "/models/wan2.2/wan2.2-t2v-14B-Q4_K_M.gguf" ]; then
    echo ""
    echo "Models not found. Starting download..."
    echo "This will download ~30-35GB. Please wait."
    echo ""
    /download-models.sh
else
    echo "Models found. Skipping download."
fi

# Symlink all model files into ComfyUI's native directories
# Supports both Q4 and Q5 variants
mkdir -p /app/ComfyUI/models/unet /app/ComfyUI/models/vae /app/ComfyUI/models/text_encoders /app/ComfyUI/models/clip_vision /app/ComfyUI/models/upscale_models /app/ComfyUI/models/controlnet

for f in /models/wan2.2/*.gguf; do
    [ -f "$f" ] && ln -sf "$f" "/app/ComfyUI/models/unet/$(basename $f)" 2>/dev/null
done
ln -sf /models/wan2.2/wan2.2-vae.safetensors /app/ComfyUI/models/vae/wan2.2-vae.safetensors 2>/dev/null
for f in /models/text-encoder/*.gguf; do
    [ -f "$f" ] && ln -sf "$f" "/app/ComfyUI/models/text_encoders/$(basename $f)" 2>/dev/null
done
ln -sf /models/clip-vision/clip-vit-large-patch14.safetensors /app/ComfyUI/models/clip_vision/clip-vit-large-patch14.safetensors 2>/dev/null
ln -sf /models/upscale/RealESRGAN_x4plus.pth /app/ComfyUI/models/upscale_models/RealESRGAN_x4plus.pth 2>/dev/null
ln -sf /models/controlnet/wan2.2-controlnet-depth.safetensors /app/ComfyUI/models/controlnet/wan2.2-controlnet-depth.safetensors 2>/dev/null
echo "Model symlinks created."

echo ""
echo "Starting ComfyUI on port 8188..."
echo "Access at: http://localhost:8188"
echo ""

# Patch: add .gguf extension support for text_encoders folder
cat > /app/ComfyUI/custom_nodes/gguf_text_encoder_patch.py << 'PYEOF'
import folder_paths
paths, exts = folder_paths.folder_names_and_paths.get("text_encoders", ([], set()))
exts.add(".gguf")
folder_paths.folder_names_and_paths["text_encoders"] = (paths, exts)
NODE_CLASS_MAPPINGS = {}
PYEOF

cd /app/ComfyUI
exec python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --output-directory /output \
    --input-directory /input \
    --disable-auto-launch
