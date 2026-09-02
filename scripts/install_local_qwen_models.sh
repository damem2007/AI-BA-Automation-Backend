#!/usr/bin/env bash
set -euo pipefail

REASONING_MODEL="${LOCAL_QWEN_REASONING_MODEL:-Qwen/Qwen3.6-35B-A3B}"
EXTRACTION_MODEL="${LOCAL_QWEN_EXTRACTION_MODEL:-Qwen/Qwen3-Omni-30B-A3B-Instruct}"
MODEL_DIR="${LOCAL_QWEN_MODEL_DIR:-./models/qwen}"
# Hugging Face metadata currently reports roughly 70.5 GB for Qwen3-Omni and
# 71.9 GB for Qwen3.6. Keep headroom for snapshots, indexes, and interrupted
# downloads so enterprise installs fail fast instead of filling the disk.
REQUIRED_BYTES="${LOCAL_QWEN_REQUIRED_BYTES:-170000000000}"

mkdir -p "${MODEL_DIR}"

available_bytes="$(df -Pk "${MODEL_DIR}" | awk 'NR==2 {print $4 * 1024}')"
if (( available_bytes < REQUIRED_BYTES )); then
  cat <<EOF
Insufficient free disk for full local Qwen download.

Available bytes: ${available_bytes}
Required bytes:  ${REQUIRED_BYTES}
Model directory: ${MODEL_DIR}

Set LOCAL_QWEN_MODEL_DIR to a volume with enough space, or free disk before
running this installer. The full public Qwen model pair is expected to require
well over 140 GB plus operational headroom.
EOF
  exit 1
fi

if ! command -v huggingface-cli >/dev/null 2>&1; then
  python -m pip install --upgrade "huggingface_hub[cli]"
fi

echo "Downloading reasoning model: ${REASONING_MODEL}"
huggingface-cli download "${REASONING_MODEL}" \
  --local-dir "${MODEL_DIR}/${REASONING_MODEL//\//__}" \
  --local-dir-use-symlinks False

echo "Downloading multimodal extraction model: ${EXTRACTION_MODEL}"
huggingface-cli download "${EXTRACTION_MODEL}" \
  --local-dir "${MODEL_DIR}/${EXTRACTION_MODEL//\//__}" \
  --local-dir-use-symlinks False

cat <<EOF

Local Qwen model files are staged under:
  ${MODEL_DIR}

Start the local inference services with:
  docker compose -f docker-compose.local-models.yml --profile local-models up -d

Expected OpenAI-compatible endpoints:
  Reasoning:  http://localhost:8001/v1
  Extraction: http://localhost:8002/v1

EOF
