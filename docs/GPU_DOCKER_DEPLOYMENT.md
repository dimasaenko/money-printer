# GPU Docker Deployment Guide

This document explains how to use GPU acceleration for `faster-whisper` subtitle generation, which dramatically increases processing speed.

## Why use GPU acceleration

The only deep-learning step in MoneyPrinterTurbo is **faster-whisper speech recognition** (converting audio into time-stamped subtitles).

- **CPU mode** (default): generating subtitles with the `large-v3` model is relatively slow
- **GPU mode**: uses an NVIDIA GPU with CUDA for a **5-10x** speedup

> Note: the other stages of the project (script generation, audio synthesis, video editing) do not involve deep learning, so GPU acceleration only affects subtitle generation.

## Deployment options

This project offers two Docker deployment paths, and **the default CPU deployment is unaffected**:

### CPU deployment (default, no changes required)

```bash
docker compose up -d
```

Uses the original `Dockerfile` (`python:3.11-slim-bullseye`). No GPU required.

### GPU deployment (for users with an NVIDIA GPU)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Uses `Dockerfile.gpu` (`nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04`) and attaches the GPU to the api service.

## Prerequisites for GPU deployment

### 1. Hardware requirements

- NVIDIA GPU (6GB VRAM or more recommended)
- The `large-v3` model uses roughly 1.5GB of VRAM on GPU at `float16` precision

### 2. Software requirements

- **NVIDIA driver**: a recent version is sufficient; run `nvidia-smi` to confirm
- **Docker Desktop**
- **NVIDIA Container Toolkit**: run `docker info` and check whether `nvidia` appears in the Runtimes list

### 3. Environment verification

```bash
# Verify that the NVIDIA driver works
nvidia-smi

# Verify that Docker supports GPUs (Runtimes should include nvidia)
docker info | findstr nvidia
```

If there is no `nvidia` runtime, you must first install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

## Configure Whisper to use the GPU

Set the following in `config.toml`:

```toml
subtitle_provider = "whisper"

[whisper]
model_size = "large-v3"
device = "cuda"           # Use GPU (CPU users should set this to "cpu")
compute_type = "float16"  # float16 is recommended on GPU (CPU users should set this to "int8")
```

## File overview

| File | Purpose |
|---|---|
| `Dockerfile` | Default CPU image (existing, unchanged) |
| `Dockerfile.gpu` | GPU image (new, based on NVIDIA CUDA) |
| `docker-compose.yml` | Default CPU deployment configuration (existing, unchanged) |
| `docker-compose.gpu.yml` | GPU deployment overlay configuration (new) |

## GPU deployment steps

### Step 1: Pull the CUDA base image

```bash
docker pull nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
```

> If you use a registry mirror such as Aliyun, it may return 403 for `nvidia/cuda`. Ensure you can pull directly from Docker Hub.

### Step 2: Update config.toml

Set `subtitle_provider = "whisper"` and `device = "cuda"` as described above.

### Step 3: Build and start

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

### Step 4: Verify that the GPU is active

```bash
docker exec -it moneyprinterturbo-api nvidia-smi
```

If GPU information is shown, the GPU has been attached successfully.

## VRAM and concurrency recommendations

| GPU VRAM | Recommended maximum concurrent tasks |
|---|---|
| 4GB | 1-2 |
| 6GB | 2-3 |
| 8GB | 3-4 |
| 12GB+ | 5 |

Concurrency is controlled via `max_concurrent_tasks` in `config.toml`.

## Troubleshooting

### Problem 1: image pull fails (403 Forbidden)

Aliyun registry mirroring returns 403 for `nvidia/cuda`. Fixes:
- Configure a different working registry mirror
- Or pull directly with `docker pull nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04`

### Problem 2: pip reports `Cannot uninstall blinker`

On Ubuntu 22.04 the system-provided `blinker` is installed via `distutils`, which pip cannot uninstall. `Dockerfile.gpu` already handles this with `apt-get remove -y python3-blinker`.

### Problem 3: `nvidia-smi` cannot find the GPU inside the container

- Confirm that the NVIDIA Container Toolkit is installed on the host
- Confirm that `nvidia` is listed in Runtimes from `docker info`
- Confirm that you used the GPU deployment command: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`

### Problem 4: Whisper reports a CUDA error

- Confirm that `device = "cuda"` in `config.toml` (case sensitive, not `"CPU"`)
- Confirm that `compute_type = "float16"`
- Confirm that `subtitle_provider = "whisper"`
