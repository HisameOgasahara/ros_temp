#!/usr/bin/env bash
set -euo pipefail

DATASET_DIR="${DATASET_DIR:-../object2_colab_augmented}"
DRIVE_ROOT="${DRIVE_ROOT:-/content/drive/MyDrive/object2_ssd_runs}"
RUN_NAME="${RUN_NAME:-$(date +%Y%m%d_%H%M%S)_mb1_ssd_object2}"
RUN_DIR="${RUN_DIR:-${DRIVE_ROOT}/${RUN_NAME}}"
PRETRAINED_MODEL="${PRETRAINED_MODEL:-models/mobilenet-v1-ssd-mp-0_675.pth}"
TENSORBOARD_PORT="${TENSORBOARD_PORT:-6006}"
START_TENSORBOARD="${START_TENSORBOARD:-0}"

mkdir -p models
mkdir -p "${RUN_DIR}"

if [ ! -f "${PRETRAINED_MODEL}" ]; then
  wget --no-check-certificate \
    https://nvidia.box.com/shared/static/djf5w54rjvpqocsiztzaandq1m3avr7c.pth \
    -O "${PRETRAINED_MODEL}"
fi

export PYTHONPATH="${PWD}/pytorch-ssd"

python tools/audit_voc_dataset.py "${DATASET_DIR}"

echo "TensorBoard logdir: ${RUN_DIR}/tensorboard"
echo "TensorBoard port: ${TENSORBOARD_PORT}"
echo "Checkpoint folder: ${RUN_DIR}"
if [ "${START_TENSORBOARD}" = "1" ]; then
  tensorboard --logdir "${RUN_DIR}/tensorboard" --host 0.0.0.0 --port "${TENSORBOARD_PORT}" >/tmp/object2_tensorboard.log 2>&1 &
fi

python mbnet/ros/train_ssd.py \
  --dataset-type voc \
  --datasets "${DATASET_DIR}" \
  --net mb1-ssd \
  --resolution 300 \
  --batch-size 16 \
  --num-workers 2 \
  --num-epochs 50 \
  --lr 0.005 \
  --base-net-lr 0.0005 \
  --pretrained-ssd "${PRETRAINED_MODEL}" \
  --checkpoint-folder "${RUN_DIR}"
