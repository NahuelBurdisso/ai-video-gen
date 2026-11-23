#!/bin/bash

MODEL_DIR="/models"

echo "=== AI Video Gen Model Downloader ==="
echo "Target directory: $MODEL_DIR"

# Create subdirectories
mkdir -p "$MODEL_DIR/wan2.2"
mkdir -p "$MODEL_DIR/text-encoder"
mkdir -p "$MODEL_DIR/clip-vision"
mkdir -p "$MODEL_DIR/upscale"
mkdir -p "$MODEL_DIR/controlnet"

FAILURES=0

download_hf() {
    local repo="$1"
    local file="$2"
    local dest="$3"
    local label="$4"

    if [ -f "$dest" ]; then
        echo "[$label] Already exists: $(basename $dest). Skipping."
        return 0
    fi

    echo "[$label] Downloading from $repo..."
    local tmpdir=$(mktemp -d)
    if ! hf download "$repo" "$file" --local-dir "$tmpdir"; then
        echo "ERROR: Failed to download $repo / $file"
        echo "Please verify this repo exists at https://huggingface.co/$repo"
        rm -rf "$tmpdir"
        FAILURES=$((FAILURES + 1))
        return 0
    fi

    # Find the downloaded file (handles nested paths like split_files/vae/file.safetensors)
    local found=$(find "$tmpdir" -name "$(basename $file)" -type f | head -1)
    if [ -n "$found" ]; then
        mv "$found" "$dest"
    else
        echo "ERROR: Downloaded but could not find $(basename $file) in $tmpdir"
        FAILURES=$((FAILURES + 1))
    fi
    rm -rf "$tmpdir"
}

# 1. Wan2.2 T2V 14B Q5 (higher quality than Q4)
download_hf \
    "city96/Wan2.1-T2V-14B-gguf" \
    "wan2.1-t2v-14b-Q5_K_M.gguf" \
    "$MODEL_DIR/wan2.2/wan2.2-t2v-14B-Q5_K_M.gguf" \
    "1/7 Wan2.2 T2V Q5"

# 2. Wan2.2 I2V 14B Q5
download_hf \
    "city96/Wan2.1-I2V-14B-480P-gguf" \
    "wan2.1-i2v-14b-480p-Q5_K_M.gguf" \
    "$MODEL_DIR/wan2.2/wan2.2-i2v-14B-Q5_K_M.gguf" \
    "2/7 Wan2.2 I2V Q5"

# 3. Wan2.2 VAE
download_hf \
    "Comfy-Org/Wan_2.1_ComfyUI_repackaged" \
    "split_files/vae/wan_2.1_vae.safetensors" \
    "$MODEL_DIR/wan2.2/wan2.2-vae.safetensors" \
    "3/7 VAE"

# 4. UMT5-XXL text encoder (Q5 for better prompt understanding)
download_hf \
    "city96/umt5-xxl-encoder-gguf" \
    "umt5-xxl-encoder-Q5_K_M.gguf" \
    "$MODEL_DIR/text-encoder/umt5-xxl-Q5.gguf" \
    "4/7 T5-XXL Q5"

# 5. CLIP Vision (for I2V)
download_hf \
    "openai/clip-vit-large-patch14" \
    "model.safetensors" \
    "$MODEL_DIR/clip-vision/clip-vit-large-patch14.safetensors" \
    "5/7 CLIP Vision"

# 6. RealESRGAN x4plus upscaler
if [ ! -f "$MODEL_DIR/upscale/RealESRGAN_x4plus.pth" ]; then
    echo "[6/7] Downloading RealESRGAN x4plus..."
    wget -q --show-progress -O "$MODEL_DIR/upscale/RealESRGAN_x4plus.pth" \
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
else
    echo "[6/7] RealESRGAN already exists. Skipping."
fi

# 7. ControlNet depth (experimental)
download_hf \
    "Kijai/Wan2.1_comfyui_controlnets" \
    "controlnet_depth.safetensors" \
    "$MODEL_DIR/controlnet/wan2.2-controlnet-depth.safetensors" \
    "7/7 ControlNet"

echo ""
if [ "$FAILURES" -gt 0 ]; then
    echo "=== WARNING: $FAILURES download(s) failed! ==="
    echo "Check errors above and retry, or download manually."
else
    echo "=== All models ready! ==="
fi
echo "Total size:"
du -sh "$MODEL_DIR" 2>/dev/null || true
