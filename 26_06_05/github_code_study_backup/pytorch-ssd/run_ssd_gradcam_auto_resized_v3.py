#!/usr/bin/env python3
"""
Run SSD inference and visualize Grad-CAM.

Usage:
  python run_ssd_gradcam.py mb1-ssd models/model.pth models/labels.txt test.jpg

Example with options:
  python run_ssd_gradcam.py mb1-ssd models/model.pth models/labels.txt test.jpg \
      --top-k 10 --threshold 0.4 --target-index 0 --show

Notes:
  - This is designed for the pytorch-ssd / jetson-inference SSD training code.
  - The CAM target is the maximum raw class score for the selected detected class.
    This explains "what image region supports this class detection" rather than the exact NMS box.
"""

import argparse
import os
import sys
from typing import Dict, Tuple, Optional

import cv2
import numpy as np
import torch
import torch.nn as nn

from vision.ssd.vgg_ssd import create_vgg_ssd, create_vgg_ssd_predictor
from vision.ssd.mobilenetv1_ssd import create_mobilenetv1_ssd, create_mobilenetv1_ssd_predictor
from vision.ssd.mobilenetv1_ssd_lite import create_mobilenetv1_ssd_lite, create_mobilenetv1_ssd_lite_predictor
from vision.ssd.squeezenet_ssd_lite import create_squeezenet_ssd_lite, create_squeezenet_ssd_lite_predictor
from vision.ssd.mobilenet_v2_ssd_lite import create_mobilenetv2_ssd_lite, create_mobilenetv2_ssd_lite_predictor


def parse_args():
    parser = argparse.ArgumentParser(description="SSD inference + Grad-CAM visualization")
    # If these are omitted, the script uses the defaults below.
    # This lets you just run:  python run_ssd_gradcam_auto.py
    parser.add_argument("net", nargs="?", default="mb1-ssd", type=str,
                        help="Network type: vgg16-ssd, mb1-ssd, mb1-ssd-lite, mb2-ssd-lite, sq-ssd-lite")
    parser.add_argument("model", nargs="?", default=os.path.join("models", "mb1-ssd-Epoch-4.pth"), type=str,
                        help="Path to trained .pth model")
    parser.add_argument("labels", nargs="?", default=os.path.join("models", "labels.txt"), type=str,
                        help="Path to labels.txt")
    parser.add_argument("image", nargs="?", default="test59.jpg", type=str,
                        help="Path to input image")
    parser.add_argument("--top-k", type=int, default=10, help="Maximum number of detections to draw")
    parser.add_argument("--threshold", type=float, default=0.2, help="Confidence threshold")
    parser.add_argument("--candidate-size", type=int, default=200, help="SSD predictor candidate size")
    parser.add_argument("--target-index", type=int, default=0,
                        help="Which detected object to explain. 0 means highest confidence detection.")
    parser.add_argument("--target-layer", type=str, default="",
                        help="Optional module name for Grad-CAM hook. If omitted, use a safer backbone layer for each net.")
    parser.add_argument("--cam-mode", type=str, default="auto", choices=["auto", "relu", "signed", "abs"],
                        help="Grad-CAM normalization mode. auto tries relu first, then signed if the CAM is flat.")
    parser.add_argument("--list-layers", action="store_true",
                        help="Print Conv2d layer names and exit")
    parser.add_argument("--cpu", action="store_true", help="Force CPU")
    parser.add_argument("--show", action="store_true", default=True, help="Show OpenCV windows. Default: true")
    parser.add_argument("--no-show", dest="show", action="store_false", help="Do not open OpenCV windows")
    parser.add_argument("--output-dir", type=str, default=".", help="Directory to save output images")
    parser.add_argument("--alpha", type=float, default=0.45, help="Heatmap overlay strength")
    parser.add_argument("--window-width", type=int, default=900, help="Maximum display window width")
    parser.add_argument("--window-height", type=int, default=700, help="Maximum display window height")
    return parser.parse_args()


def load_class_names(label_path: str):
    with open(label_path, "r") as f:
        return [name.strip() for name in f.readlines() if name.strip()]


def create_net_and_predictor(net_type: str, num_classes: int, model_path: str, candidate_size: int, device: torch.device):
    if net_type == "vgg16-ssd":
        net = create_vgg_ssd(num_classes, is_test=True)
        predictor_fn = create_vgg_ssd_predictor
    elif net_type == "mb1-ssd":
        net = create_mobilenetv1_ssd(num_classes, is_test=True)
        predictor_fn = create_mobilenetv1_ssd_predictor
    elif net_type == "mb1-ssd-lite":
        net = create_mobilenetv1_ssd_lite(num_classes, is_test=True)
        predictor_fn = create_mobilenetv1_ssd_lite_predictor
    elif net_type == "mb2-ssd-lite":
        net = create_mobilenetv2_ssd_lite(num_classes, is_test=True)
        predictor_fn = create_mobilenetv2_ssd_lite_predictor
    elif net_type == "sq-ssd-lite":
        net = create_squeezenet_ssd_lite(num_classes, is_test=True)
        predictor_fn = create_squeezenet_ssd_lite_predictor
    else:
        raise ValueError("Invalid net type. Use one of: vgg16-ssd, mb1-ssd, mb1-ssd-lite, mb2-ssd-lite, sq-ssd-lite")

    net.load(model_path)
    net.to(device)
    net.eval()

    # predictor handles the same preprocessing and postprocessing as the original example script.
    predictor = predictor_fn(net, candidate_size=candidate_size, device=device)
    return net, predictor


def get_module_by_name(model: nn.Module, name: str) -> nn.Module:
    modules = dict(model.named_modules())
    if name not in modules:
        raise KeyError(f"Cannot find target layer '{name}'. Use --list-layers to inspect names.")
    return modules[name]


def list_conv_layers(model: nn.Module):
    for name, module in model.named_modules():
        if isinstance(module, nn.Conv2d):
            print(name)


def find_default_target_layer(model: nn.Module, net_type: str = "") -> Tuple[str, nn.Module]:
    """
    Pick a useful convolutional feature layer for Grad-CAM.

    Very late SSD extra layers can be spatially tiny and sometimes produce an almost
    all-zero ReLU Grad-CAM. For MobileNetV1-SSD, a late backbone layer is usually
    more interpretable than extras.
    """
    modules = dict(model.named_modules())

    # Good first guesses for qfgaohao / jetson-inference pytorch-ssd models.
    preferred_by_net = {
        "mb1-ssd": [
            "base_net.12.0", "base_net.11.0", "base_net.10.0",
            "source_layer_add_ons.0", "extras.0.0"
        ],
        "mb1-ssd-lite": [
            "base_net.12.0", "base_net.11.0", "base_net.10.0",
            "source_layer_add_ons.0", "extras.0.0"
        ],
        "mb2-ssd-lite": [
            "base_net.17.conv.3", "base_net.16.conv.3", "base_net.14.conv.3",
            "extras.0.0"
        ],
        "vgg16-ssd": [
            "base_net.28", "base_net.27", "source_layer_add_ons.0", "extras.0.0"
        ],
        "sq-ssd-lite": [
            "base_net.12", "base_net.11", "extras.0.0"
        ],
    }

    for name in preferred_by_net.get(net_type, []):
        layer = modules.get(name)
        if isinstance(layer, nn.Conv2d):
            return name, layer

    preferred_prefixes = ("base_net", "source_layer_add_ons")
    excluded_tokens = ("classification_headers", "regression_headers")

    candidates = []
    for name, module in model.named_modules():
        if isinstance(module, nn.Conv2d):
            if any(tok in name for tok in excluded_tokens):
                continue
            if name.startswith(preferred_prefixes):
                candidates.append((name, module))

    if candidates:
        return candidates[-1]

    candidates = []
    for name, module in model.named_modules():
        if isinstance(module, nn.Conv2d) and not any(tok in name for tok in excluded_tokens):
            candidates.append((name, module))

    if not candidates:
        raise RuntimeError("No Conv2d layer found for Grad-CAM.")

    return candidates[-1]


class GradCAM:
    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.target_layer = target_layer
        self.activations: Optional[torch.Tensor] = None
        self.gradients: Optional[torch.Tensor] = None
        self.handle = self.target_layer.register_forward_hook(self._forward_hook)

    def _forward_hook(self, module, inputs, output):
        self.activations = output
        output.register_hook(self._save_gradient)

    def _save_gradient(self, grad):
        self.gradients = grad

    def remove(self):
        self.handle.remove()

    def __call__(self, input_tensor: torch.Tensor, class_index: int, mode: str = "auto") -> np.ndarray:
        self.model.zero_grad(set_to_none=True)

        scores, _boxes = self.model(input_tensor)

        if scores.dim() == 3:
            target_score = scores[0, :, class_index].max()
        elif scores.dim() == 2:
            target_score = scores[:, class_index].max()
        else:
            raise RuntimeError(f"Unexpected SSD score tensor shape: {tuple(scores.shape)}")

        target_score.backward(retain_graph=True)

        if self.activations is None or self.gradients is None:
            raise RuntimeError("Grad-CAM hooks did not capture activations/gradients.")

        activations = self.activations.detach()
        gradients = self.gradients.detach()
        weights = gradients.mean(dim=(2, 3), keepdim=True)
        raw_cam = (weights * activations).sum(dim=1, keepdim=False)[0]

        def normalize(x: torch.Tensor) -> torch.Tensor:
            x = x - x.min()
            denom = x.max()
            if float(denom.detach().cpu()) < 1e-12:
                return torch.zeros_like(x)
            return x / denom

        relu_cam = normalize(torch.relu(raw_cam))
        relu_max = float(relu_cam.max().detach().cpu())

        if mode == "relu":
            cam = relu_cam
            used_mode = "relu"
        elif mode == "signed":
            cam = normalize(raw_cam)
            used_mode = "signed"
        elif mode == "abs":
            cam = normalize(raw_cam.abs())
            used_mode = "abs"
        else:
            if relu_max < 1e-6:
                cam = normalize(raw_cam)
                used_mode = "signed-fallback"
            else:
                cam = relu_cam
                used_mode = "relu"

        print(
            f"Grad-CAM stats: mode={used_mode}, "
            f"raw_min={float(raw_cam.min().detach().cpu()):.6g}, "
            f"raw_max={float(raw_cam.max().detach().cpu()):.6g}, "
            f"relu_max={relu_max:.6g}"
        )

        return cam.cpu().numpy()


def make_overlay(orig_bgr: np.ndarray, cam_small: np.ndarray, alpha: float = 0.45) -> Tuple[np.ndarray, np.ndarray]:
    h, w = orig_bgr.shape[:2]
    cam = cv2.resize(cam_small, (w, h))
    heatmap_uint8 = np.uint8(255 * cam)
    heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(orig_bgr, 1.0 - alpha, heatmap_color, alpha, 0)
    return heatmap_color, overlay


def draw_detections(image_bgr: np.ndarray, boxes, labels, probs, class_names):
    out = image_bgr.copy()
    for i in range(boxes.size(0)):
        box = boxes[i, :].detach().cpu().numpy().astype(int)
        label_idx = int(labels[i].detach().cpu().item())
        prob = float(probs[i].detach().cpu().item())

        x1, y1, x2, y2 = box.tolist()
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 255, 0), 3)
        text = f"{i}: {class_names[label_idx]} {prob:.2f}"
        cv2.putText(out, text, (x1, max(25, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 0, 255), 2)
    return out



def show_resized(win_name: str, img: np.ndarray, max_width: int = 900, max_height: int = 700):
    """Show image in a resized OpenCV window without changing saved output size."""
    h, w = img.shape[:2]
    if h <= 0 or w <= 0:
        raise ValueError(f"Invalid image size for window '{win_name}': {w}x{h}")

    scale = min(max_width / float(w), max_height / float(h), 1.0)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    if scale < 1.0:
        shown = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    else:
        shown = img

    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, new_w, new_h)
    cv2.imshow(win_name, shown)

def main():
    args = parse_args()

    device = torch.device("cpu" if args.cpu or not torch.cuda.is_available() else "cuda:0")
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Net:    {args.net}")
    print(f"Model:  {args.model}")
    print(f"Labels: {args.labels}")
    print(f"Image:  {args.image}")

    class_names = load_class_names(args.labels)
    net, predictor = create_net_and_predictor(
        args.net, len(class_names), args.model, args.candidate_size, device
    )

    if args.list_layers:
        list_conv_layers(net)
        return

    orig_bgr = cv2.imread(args.image)
    if orig_bgr is None:
        raise IOError(f"Cannot read image: {args.image}")
    rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)

    boxes, labels, probs = predictor.predict(rgb, args.top_k, args.threshold)
    det_bgr = draw_detections(orig_bgr, boxes, labels, probs, class_names)

    base = os.path.splitext(os.path.basename(args.image))[0]
    det_path = os.path.join(args.output_dir, f"{base}_ssd_detections.jpg")
    cv2.imwrite(det_path, det_bgr)

    if boxes.size(0) == 0:
        print(f"No objects found above threshold {args.threshold}.")
        print(f"Saved detection image: {det_path}")
        if args.show:
            show_resized("SSD detections", det_bgr, args.window_width, args.window_height)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return

    target_index = max(0, min(args.target_index, boxes.size(0) - 1))
    target_label = int(labels[target_index].detach().cpu().item())
    target_prob = float(probs[target_index].detach().cpu().item())
    target_name = class_names[target_label]

    if args.target_layer:
        target_layer_name = args.target_layer
        target_layer = get_module_by_name(net, args.target_layer)
    else:
        target_layer_name, target_layer = find_default_target_layer(net, args.net)

    print(f"Device: {device}")
    print(f"Found {boxes.size(0)} objects")
    print(f"Grad-CAM target detection: index={target_index}, class={target_name}, confidence={target_prob:.4f}")
    print(f"Grad-CAM target layer: {target_layer_name}")

    # Use the exact preprocessing used by the predictor.
    input_tensor = predictor.transform(rgb).unsqueeze(0).to(device)
    input_tensor.requires_grad_(True)

    gradcam = GradCAM(net, target_layer)
    try:
        cam = gradcam(input_tensor, target_label, mode=args.cam_mode)
    finally:
        gradcam.remove()

    heatmap_bgr, overlay_bgr = make_overlay(det_bgr, cam, alpha=args.alpha)

    heatmap_path = os.path.join(args.output_dir, f"{base}_gradcam_heatmap.jpg")
    overlay_path = os.path.join(args.output_dir, f"{base}_gradcam_overlay.jpg")
    cv2.imwrite(heatmap_path, heatmap_bgr)
    cv2.imwrite(overlay_path, overlay_bgr)

    print(f"Saved detection image: {det_path}")
    print(f"Saved raw heatmap:      {heatmap_path}")
    print(f"Saved overlay image:   {overlay_path}")

    if args.show:
        show_resized("SSD detections", det_bgr, args.window_width, args.window_height)
        show_resized("Grad-CAM heatmap", heatmap_bgr, args.window_width, args.window_height)
        show_resized("Grad-CAM overlay", overlay_bgr, args.window_width, args.window_height)
        print("Press any key on an image window to close.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
