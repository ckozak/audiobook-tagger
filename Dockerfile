FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3.10-venv python3-pip \
    ffmpeg git curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Install Python packages
RUN pip install --upgrade pip
RUN pip install torch --index-url https://download.pytorch.org/whl/cu121

RUN pip install faster-whisper
RUN pip install ebooklib
RUN pip install beautifulsoup4
RUN pip install rapidfuzz
RUN pip install sentence-transformers
RUN pip install mutagen
RUN pip install tbm-utils

WORKDIR /app
COPY . .

CMD ["python", "transcribe.py"]