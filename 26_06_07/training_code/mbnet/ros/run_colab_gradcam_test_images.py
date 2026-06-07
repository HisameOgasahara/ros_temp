#!/usr/bin/env python3
"""
Run MobileNetV1-SSD detection + Grad-CAM on VOC test images in Colab.

This script is intended for the object2 Colab workflow:
  - trained checkpoints are under Google Drive run folders
  - test images are read from ImageSets/Main/test.txt
  - each output is a 2x2 panel: Original, Heatmap, Detections, Overlay+Detections
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


CHECKPOINT_RE = re.compile(r"Epoch-(?P<epoch>\d+)-Loss-(?P<loss>[0-9.eE+-]+)\.pth$")


def parse_args():
    parser = argparse.ArgumentParser(description="Colab batch SSD Grad-CAM viewer for VOC test images")
    parser.add_argument("--run-dir", required=True, help="Drive run folder containing .pth checkpoints and labels.txt")
    parser.add_argument("--dataset", default="/content/object2_work/object2_colab_augmented", help="VOC dataset root")
    parser.add_argument("--model", default="", help="Specific .pth path. If omitted, --epoch is used.")
    parser.add_argument("--epoch", type=int, default=20, help="Checkpoint epoch to load. Use -1 for best loss in run-dir.")
    parser.add_argument("--labels", default="", help="labels.txt path. Defaults to <run-dir>/labels.txt")
    parser.add_argument("--split", default="test", help="VOC split name under ImageSets/Main, usually test")
    parser.add_argument("--num-images", type=int, default=12, help="Number of split images to visualize")
    parser.add_argument("--start-index", type=int, default=0, help="Start offset inside the split file")
    parser.add_argument("--net", default="mb1-ssd", help="SSD network type")
    parser.add_argument("--top-k", type=int, default=10, help="Maximum detections per image")
    parser.add_argument("--threshold", type=float, default=0.4, help="Detection confidence threshold")
    parser.add_argument("--candidate-size", type=int, default=200, help="SSD predictor candidate size")
    parser.add_argument("--target-layer", default="", help="Optional Grad-CAM layer name")
    parser.add_argument("--cam-mode", default="auto", choices=["auto", "relu", "signed", "abs"])
    parser.add_argument("--alpha", type=float, default=0.45, help="Heatmap overlay strength")
    parser.add_argument("--output-dir", default="", help="Output dir. Defaults to <run-dir>/gradcam_test_outputs")
    parser.add_argument("--display", action="store_true", help="Display saved panels inline when run inside Colab/IPython")
    parser.add_argument("--cpu", action="store_true", help="Force CPU")
    return parser.parse_args()


def checkpoint_info(path: Path) -> Optional[Tuple[int, float]]:
    match = CHECKPOINT_RE.search(path.name)
    if not match:
        return None
    return int(match.group("epoch")), float(match.group("loss"))


def find_checkpoint(run_dir: Path, epoch: Optional[int] = 20) -> Path:
    checkpoints = []
    for path in run_dir.glob("*.pth"):
        info = checkpoint_info(path)
        if info is None:
            continue
        ckpt_epoch, loss = info
        if epoch is None or ckpt_epoch == epoch:
            checkpoints.append((loss, ckpt_epoch, path))

    if not checkpoints:
        if epoch is None:
            raise FileNotFoundError(f"No checkpoint files matching '*Epoch-*-Loss-*.pth' in {run_dir}")
        raise FileNotFoundError(f"No checkpoint for Epoch-{epoch} in {run_dir}")

    checkpoints.sort(key=lambda item: (item[0], item[1], item[2].name))
    return checkpoints[0][2]


def read_split_ids(split_path: Path) -> List[str]:
    return [line.strip() for line in split_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def image_path_for_id(dataset: Path, image_id: str) -> Path:
    for suffix in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"):
        candidate = dataset / "JPEGImages" / f"{image_id}{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Cannot find image for id '{image_id}' under {dataset / 'JPEGImages'}")


def put_title(cv2, image, title: str):
    out = image.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 34), (20, 20, 20), -1)
    cv2.putText(out, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return out


def fit_to_cell(cv2, np, image, width: int, height: int):
    h, w = image.shape[:2]
    scale = min(width / float(w), height / float(h))
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width, 3), dtype=image.dtype)
    x = (width - new_w) // 2
    y = (height - new_h) // 2
    canvas[y:y + new_h, x:x + new_w] = resized
    return canvas


def make_panel(cv2, np, original_bgr, heatmap_bgr, detections_bgr, overlay_bgr, title: str):
    h, w = original_bgr.shape[:2]
    cell_w = min(max(w, 480), 900)
    cell_h = min(max(h, 360), 700)

    panels = [
        put_title(cv2, original_bgr, "Original"),
        put_title(cv2, heatmap_bgr, "Grad-CAM Heatmap"),
        put_title(cv2, detections_bgr, "Detections"),
        put_title(cv2, overlay_bgr, "Overlay + Detections"),
    ]
    cells = [fit_to_cell(cv2, np, panel, cell_w, cell_h) for panel in panels]
    top = np.hstack([cells[0], cells[1]])
    bottom = np.hstack([cells[2], cells[3]])
    panel = np.vstack([top, bottom])
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 38), (0, 0, 0), -1)
    cv2.putText(panel, title, (12, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (255, 255, 255), 2)
    return panel


def import_gradcam_helpers():
    script_dir = Path(__file__).resolve().parent
    training_root = script_dir.parents[1]
    pytorch_ssd = training_root / "pytorch-ssd"
    for path in (str(script_dir), str(pytorch_ssd)):
        if path not in sys.path:
            sys.path.insert(0, path)

    import cv2
    import numpy as np
    import torch
    from run_ssd_gradcam_auto_resized_v3 import (
        GradCAM,
        create_net_and_predictor,
        find_default_target_layer,
        get_module_by_name,
        load_class_names,
        make_overlay,
    )

    return cv2, np, torch, {
        "GradCAM": GradCAM,
        "create_net_and_predictor": create_net_and_predictor,
        "find_default_target_layer": find_default_target_layer,
        "get_module_by_name": get_module_by_name,
        "load_class_names": load_class_names,
        "make_overlay": make_overlay,
    }


def draw_detections(cv2, image_bgr, boxes, labels, probs, class_names):
    out = image_bgr.copy()
    rows = []
    colors = [(0, 220, 255), (255, 160, 0), (80, 255, 80), (255, 80, 220), (180, 180, 255)]
    for i in range(boxes.size(0)):
        box = boxes[i, :].detach().cpu().numpy().astype(int)
        label_idx = int(labels[i].detach().cpu().item())
        prob = float(probs[i].detach().cpu().item())
        name = class_names[label_idx] if label_idx < len(class_names) else str(label_idx)
        x1, y1, x2, y2 = box.tolist()
        color = colors[i % len(colors)]
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 3)
        text = f"{i}: {name} {prob:.2f}"
        cv2.putText(out, text, (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        rows.append((i, name, prob, x1, y1, x2, y2))
    return out, rows


def run_image(cv2, np, torch, helpers, net, predictor, class_names: Sequence[str], image_path: Path, args, device):
    original_bgr = cv2.imread(str(image_path))
    if original_bgr is None:
        raise IOError(f"Cannot read image: {image_path}")
    rgb = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2RGB)

    boxes, labels, probs = predictor.predict(rgb, args.top_k, args.threshold)
    detections_bgr, rows = draw_detections(cv2, original_bgr, boxes, labels, probs, class_names)

    if boxes.size(0) == 0:
        heatmap_bgr = np.zeros_like(original_bgr)
        overlay_bgr = detections_bgr.copy()
        title = f"{image_path.stem} | no detections above {args.threshold}"
        return make_panel(cv2, np, original_bgr, heatmap_bgr, detections_bgr, overlay_bgr, title), rows

    target_label = int(labels[0].detach().cpu().item())
    target_prob = float(probs[0].detach().cpu().item())
    target_name = class_names[target_label] if target_label < len(class_names) else str(target_label)

    if args.target_layer:
        target_layer_name = args.target_layer
        target_layer = helpers["get_module_by_name"](net, args.target_layer)
    else:
        target_layer_name, target_layer = helpers["find_default_target_layer"](net, args.net)

    input_tensor = predictor.transform(rgb).unsqueeze(0).to(device)
    input_tensor.requires_grad_(True)

    gradcam = helpers["GradCAM"](net, target_layer)
    try:
        cam = gradcam(input_tensor, target_label, mode=args.cam_mode)
    finally:
        gradcam.remove()

    heatmap_bgr, overlay_bgr = helpers["make_overlay"](detections_bgr, cam, alpha=args.alpha)
    title = f"{image_path.stem} | target={target_name} {target_prob:.2f} | layer={target_layer_name}"
    return make_panel(cv2, np, original_bgr, heatmap_bgr, detections_bgr, overlay_bgr, title), rows


def display_images(paths: Sequence[Path]):
    try:
        from IPython.display import Image, display
    except Exception:
        print("IPython display is unavailable. Saved files:")
        for path in paths:
            print(path)
        return

    for path in paths:
        display(Image(filename=str(path)))


def main():
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser()
    dataset = Path(args.dataset).expanduser()
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else run_dir / "gradcam_test_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = Path(args.model).expanduser() if args.model else find_checkpoint(
        run_dir, epoch=None if args.epoch < 0 else args.epoch
    )
    labels_path = Path(args.labels).expanduser() if args.labels else run_dir / "labels.txt"
    split_path = dataset / "ImageSets" / "Main" / f"{args.split}.txt"

    image_ids = read_split_ids(split_path)
    selected_ids = image_ids[args.start_index:args.start_index + args.num_images]
    if not selected_ids:
        raise ValueError(f"No image ids selected from {split_path}")

    cv2, np, torch, helpers = import_gradcam_helpers()
    device = torch.device("cpu" if args.cpu or not torch.cuda.is_available() else "cuda:0")

    class_names = helpers["load_class_names"](str(labels_path))
    net, predictor = helpers["create_net_and_predictor"](
        args.net, len(class_names), str(model_path), args.candidate_size, device
    )

    print(f"Device:  {device}")
    print(f"Model:   {model_path}")
    print(f"Labels:  {labels_path}")
    print(f"Dataset: {dataset}")
    print(f"Split:   {split_path}")
    print(f"Output:  {output_dir}")

    saved = []
    for index, image_id in enumerate(selected_ids, start=args.start_index):
        image_path = image_path_for_id(dataset, image_id)
        panel, rows = run_image(cv2, np, torch, helpers, net, predictor, class_names, image_path, args, device)
        output_path = output_dir / f"{index:03d}_{image_id}_gradcam_panel.jpg"
        cv2.imwrite(str(output_path), panel)
        saved.append(output_path)
        summary = ", ".join(f"{name}:{prob:.2f}" for _i, name, prob, *_box in rows) or "no detections"
        print(f"[{index}] {image_id}: {summary}")

    if args.display:
        display_images(saved)


if __name__ == "__main__":
    main()
