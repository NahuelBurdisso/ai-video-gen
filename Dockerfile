FROM nvidia/cuda:12.6.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System deps + deadsnakes PPA for Python 3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set python3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Install pip for python3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# PyTorch with CUDA 12.6
RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

# Clone ComfyUI
WORKDIR /app
RUN git clone https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /app/ComfyUI

# Install ComfyUI requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install huggingface-cli
RUN pip install --no-cache-dir huggingface_hub[cli]

# Install ComfyUI-Manager
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git custom_nodes/ComfyUI-Manager

# Install custom nodes
RUN git clone https://github.com/city96/ComfyUI-GGUF.git custom_nodes/ComfyUI-GGUF && \
    pip install --no-cache-dir -r custom_nodes/ComfyUI-GGUF/requirements.txt

RUN git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git custom_nodes/ComfyUI-WanVideoWrapper && \
    pip install --no-cache-dir -r custom_nodes/ComfyUI-WanVideoWrapper/requirements.txt

RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git custom_nodes/ComfyUI-VideoHelperSuite && \
    pip install --no-cache-dir -r custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt

RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git custom_nodes/ComfyUI-KJNodes && \
    pip install --no-cache-dir -r custom_nodes/ComfyUI-KJNodes/requirements.txt

RUN git clone https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet.git custom_nodes/ComfyUI-Advanced-ControlNet && \
    cd custom_nodes/ComfyUI-Advanced-ControlNet && pip install --no-cache-dir . 2>/dev/null || true

# SageAttention for faster attention computation
RUN pip install --no-cache-dir sageattention

# Copy scripts
COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/download-models.sh /download-models.sh
RUN chmod +x /entrypoint.sh /download-models.sh

EXPOSE 8188

ENTRYPOINT ["/entrypoint.sh"]
