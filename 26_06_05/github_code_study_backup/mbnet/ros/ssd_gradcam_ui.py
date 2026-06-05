#!/usr/bin/env python3
import argparse
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parents[2]
PYTORCH_SSD = ROOT / "pytorch-ssd"
if str(PYTORCH_SSD) not in sys.path:
    sys.path.insert(0, str(PYTORCH_SSD))

from vision.ssd.vgg_ssd import create_vgg_ssd, create_vgg_ssd_predictor
from vision.ssd.mobilenetv1_ssd import create_mobilenetv1_ssd, create_mobilenetv1_ssd_predictor
from vision.ssd.mobilenetv1_ssd_lite import create_mobilenetv1_ssd_lite, create_mobilenetv1_ssd_lite_predictor
from vision.ssd.squeezenet_ssd_lite import create_squeezenet_ssd_lite, create_squeezenet_ssd_lite_predictor
from vision.ssd.mobilenet_v2_ssd_lite import create_mobilenetv2_ssd_lite, create_mobilenetv2_ssd_lite_predictor


def load_class_names(label_path: str):
    text = Path(label_path).read_text(encoding="utf-8").strip()
    if "," in text and "\n" not in text:
        labels = [part.strip() for part in text.split(",") if part.strip()]
        if labels and labels[0].upper() != "BACKGROUND":
            labels.insert(0, "BACKGROUND")
        return labels
    return [line.strip() for line in text.splitlines() if line.strip()]


def latest_model_path() -> str:
    model_dir = ROOT / "mbnet" / "ros" / "models"
    models = sorted(model_dir.glob("*.pth"), key=lambda p: p.stat().st_mtime, reverse=True)
    if models:
        return str(models[0])
    return ""


def default_labels_path() -> str:
    preferred = ROOT / "mbnet" / "ros" / "models" / "labels.txt"
    if preferred.exists():
        return str(preferred)
    fallback = ROOT / "mbnet" / "ros" / "labels.txt"
    return str(fallback) if fallback.exists() else ""


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
        raise ValueError(f"Unsupported net type: {net_type}")

    net.load(model_path)
    net.to(device)
    net.eval()
    predictor = predictor_fn(net, candidate_size=candidate_size, device=device)
    return net, predictor


def get_module_by_name(model: nn.Module, name: str) -> nn.Module:
    modules = dict(model.named_modules())
    if name not in modules:
        raise KeyError(f"Cannot find target layer '{name}'")
    return modules[name]


def find_default_target_layer(model: nn.Module, net_type: str = "") -> Tuple[str, nn.Module]:
    modules = dict(model.named_modules())
    preferred_by_net = {
        "mb1-ssd": ["base_net.12.0", "base_net.11.0", "base_net.10.0", "source_layer_add_ons.0", "extras.0.0"],
        "mb1-ssd-lite": ["base_net.12.0", "base_net.11.0", "base_net.10.0", "source_layer_add_ons.0", "extras.0.0"],
        "mb2-ssd-lite": ["base_net.17.conv.3", "base_net.16.conv.3", "base_net.14.conv.3", "extras.0.0"],
        "vgg16-ssd": ["base_net.28", "base_net.27", "source_layer_add_ons.0", "extras.0.0"],
        "sq-ssd-lite": ["base_net.12", "base_net.11", "extras.0.0"],
    }
    for name in preferred_by_net.get(net_type, []):
        layer = modules.get(name)
        if isinstance(layer, nn.Conv2d):
            return name, layer

    candidates = []
    excluded = ("classification_headers", "regression_headers")
    for name, module in model.named_modules():
        if isinstance(module, nn.Conv2d) and not any(token in name for token in excluded):
            candidates.append((name, module))
    if not candidates:
        raise RuntimeError("No Conv2d layer found for Grad-CAM")
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
            raise RuntimeError("Grad-CAM hooks did not capture activations/gradients")

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
        if mode == "relu":
            cam = relu_cam
        elif mode == "signed":
            cam = normalize(raw_cam)
        elif mode == "abs":
            cam = normalize(raw_cam.abs())
        else:
            cam = normalize(raw_cam) if float(relu_cam.max().detach().cpu()) < 1e-6 else relu_cam
        return cam.cpu().numpy()


def draw_detections(image_bgr: np.ndarray, boxes, labels, probs, class_names):
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


def make_overlay(orig_bgr: np.ndarray, cam_small: np.ndarray, alpha: float = 0.45):
    h, w = orig_bgr.shape[:2]
    cam = cv2.resize(cam_small, (w, h))
    heatmap_uint8 = np.uint8(255 * cam)
    heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(orig_bgr, 1.0 - alpha, heatmap_color, alpha, 0)
    return heatmap_color, overlay


def bgr_to_photo(image_bgr: np.ndarray, max_w: int, max_h: int):
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    scale = min(max_w / w, max_h / h, 1.0)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    pil = Image.fromarray(rgb).resize(new_size, Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(pil)


def read_image_bgr(path: str):
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


class SSDGradCamApp:
    def __init__(self, root: tk.Tk, args):
        self.root = root
        self.args = args
        self.root.title("SSD Grad-CAM Tester")
        self.root.geometry("1420x920")

        self.device = torch.device("cpu" if args.cpu or not torch.cuda.is_available() else "cuda:0")
        self.net = None
        self.predictor = None
        self.class_names = None
        self.loaded_key = None
        self.current_image_path = ""
        self.photos = {}

        self.net_var = tk.StringVar(value=args.net)
        self.model_var = tk.StringVar(value=args.model or latest_model_path())
        self.labels_var = tk.StringVar(value=args.labels or default_labels_path())
        self.threshold_var = tk.DoubleVar(value=args.threshold)
        self.topk_var = tk.IntVar(value=args.top_k)
        self.target_var = tk.IntVar(value=0)
        self.alpha_var = tk.DoubleVar(value=args.alpha)
        self.layer_var = tk.StringVar(value=args.target_layer)
        self.cam_mode_var = tk.StringVar(value=args.cam_mode)
        self.status_var = tk.StringVar(value=f"Ready. Device: {self.device}")

        self._build_ui()
        if args.image:
            self.load_image(args.image)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Net").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        ttk.Combobox(controls, textvariable=self.net_var, width=14, values=["mb1-ssd", "mb1-ssd-lite", "mb2-ssd-lite", "sq-ssd-lite", "vgg16-ssd"], state="readonly").grid(row=0, column=1, sticky=tk.W)

        ttk.Label(controls, text="Model").grid(row=0, column=2, sticky=tk.W, padx=(12, 6))
        ttk.Entry(controls, textvariable=self.model_var, width=68).grid(row=0, column=3, sticky=tk.EW)
        ttk.Button(controls, text="Browse", command=self.choose_model).grid(row=0, column=4, padx=6)

        ttk.Label(controls, text="Labels").grid(row=1, column=2, sticky=tk.W, padx=(12, 6), pady=(8, 0))
        ttk.Entry(controls, textvariable=self.labels_var, width=68).grid(row=1, column=3, sticky=tk.EW, pady=(8, 0))
        ttk.Button(controls, text="Browse", command=self.choose_labels).grid(row=1, column=4, padx=6, pady=(8, 0))
        controls.columnconfigure(3, weight=1)

        opts = ttk.Frame(outer)
        opts.pack(fill=tk.X, pady=(10, 10))
        ttk.Button(opts, text="Open Image", command=self.choose_image).pack(side=tk.LEFT)
        ttk.Button(opts, text="Run", command=self.run_current).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(opts, text="Threshold").pack(side=tk.LEFT)
        ttk.Spinbox(opts, from_=0.01, to=0.99, increment=0.05, textvariable=self.threshold_var, width=6).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(opts, text="Top K").pack(side=tk.LEFT)
        ttk.Spinbox(opts, from_=1, to=50, increment=1, textvariable=self.topk_var, width=5).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(opts, text="Target").pack(side=tk.LEFT)
        ttk.Spinbox(opts, from_=0, to=49, increment=1, textvariable=self.target_var, width=5).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(opts, text="Alpha").pack(side=tk.LEFT)
        ttk.Spinbox(opts, from_=0.05, to=0.95, increment=0.05, textvariable=self.alpha_var, width=6).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(opts, text="CAM").pack(side=tk.LEFT)
        ttk.Combobox(opts, textvariable=self.cam_mode_var, width=8, values=["auto", "relu", "signed", "abs"], state="readonly").pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(opts, text="Layer").pack(side=tk.LEFT)
        ttk.Entry(opts, textvariable=self.layer_var, width=22).pack(side=tk.LEFT, padx=(4, 0))

        body = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=4)
        body.add(right, weight=1)

        grid = ttk.Frame(left)
        grid.pack(fill=tk.BOTH, expand=True)
        self.image_labels = {}
        for idx, title in enumerate(["Original", "Detections", "Grad-CAM Heatmap", "Overlay"]):
            frame = ttk.LabelFrame(grid, text=title, padding=6)
            frame.grid(row=idx // 2, column=idx % 2, sticky=tk.NSEW, padx=5, pady=5)
            label = ttk.Label(frame, anchor=tk.CENTER)
            label.pack(fill=tk.BOTH, expand=True)
            self.image_labels[title] = label
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        ttk.Label(right, text="Detections").pack(anchor=tk.W)
        columns = ("idx", "class", "prob", "box")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", height=18)
        for col, width in [("idx", 42), ("class", 110), ("prob", 70), ("box", 180)]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self.tree.bind("<<TreeviewSelect>>", self.on_detection_select)

        ttk.Label(right, textvariable=self.status_var, wraplength=360).pack(fill=tk.X, anchor=tk.W)

    def choose_model(self):
        path = filedialog.askopenfilename(filetypes=[("PyTorch model", "*.pth"), ("All files", "*.*")])
        if path:
            self.model_var.set(path)
            self.loaded_key = None

    def choose_labels(self):
        path = filedialog.askopenfilename(filetypes=[("Labels", "*.txt"), ("All files", "*.*")])
        if path:
            self.labels_var.set(path)
            self.loaded_key = None

    def choose_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All files", "*.*")])
        if path:
            self.load_image(path)

    def load_image(self, path: str):
        self.current_image_path = path
        image = read_image_bgr(path)
        if image is None:
            messagebox.showerror("Image error", f"Cannot read image:\n{path}")
            return
        self.set_image("Original", image)
        self.status_var.set(f"Loaded image: {path}")
        self.run_current()

    def on_detection_select(self, _event):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if values:
            self.target_var.set(int(values[0]))

    def run_current(self):
        if not self.current_image_path:
            self.choose_image()
            return
        self.status_var.set("Running inference...")
        thread = threading.Thread(target=self._run_inference_thread, daemon=True)
        thread.start()

    def _load_model_if_needed(self):
        key = (self.net_var.get(), self.model_var.get(), self.labels_var.get(), int(self.topk_var.get()), str(self.device))
        if self.loaded_key == key and self.net is not None:
            return
        if not self.model_var.get() or not Path(self.model_var.get()).exists():
            raise FileNotFoundError("Choose a trained .pth model file before running inference.")
        if not self.labels_var.get() or not Path(self.labels_var.get()).exists():
            raise FileNotFoundError("Choose a labels.txt file before running inference.")
        self.class_names = load_class_names(self.labels_var.get())
        self.net, self.predictor = create_net_and_predictor(
            self.net_var.get(), len(self.class_names), self.model_var.get(), int(self.topk_var.get()) * 40, self.device
        )
        self.loaded_key = key

    def _run_inference_thread(self):
        try:
            self._load_model_if_needed()
            orig_bgr = read_image_bgr(self.current_image_path)
            if orig_bgr is None:
                raise IOError(f"Cannot read image: {self.current_image_path}")
            rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)

            boxes, labels, probs = self.predictor.predict(rgb, int(self.topk_var.get()), float(self.threshold_var.get()))
            det_bgr, rows = draw_detections(orig_bgr, boxes, labels, probs, self.class_names)

            heatmap_bgr = np.zeros_like(orig_bgr)
            overlay_bgr = det_bgr.copy()
            status = f"Found {len(rows)} objects. Device: {self.device}"

            if boxes.size(0) > 0:
                target_index = max(0, min(int(self.target_var.get()), boxes.size(0) - 1))
                target_label = int(labels[target_index].detach().cpu().item())
                target_name = self.class_names[target_label] if target_label < len(self.class_names) else str(target_label)
                if self.layer_var.get().strip():
                    layer_name = self.layer_var.get().strip()
                    target_layer = get_module_by_name(self.net, layer_name)
                else:
                    layer_name, target_layer = find_default_target_layer(self.net, self.net_var.get())

                input_tensor = self.predictor.transform(rgb).unsqueeze(0).to(self.device)
                input_tensor.requires_grad_(True)
                gradcam = GradCAM(self.net, target_layer)
                try:
                    cam = gradcam(input_tensor, target_label, mode=self.cam_mode_var.get())
                finally:
                    gradcam.remove()
                heatmap_bgr, overlay_bgr = make_overlay(det_bgr, cam, alpha=float(self.alpha_var.get()))
                prob = float(probs[target_index].detach().cpu().item())
                status = f"Found {len(rows)} objects. CAM target {target_index}: {target_name} {prob:.3f}, layer {layer_name}. Device: {self.device}"

            self.root.after(0, lambda: self._apply_results(orig_bgr, det_bgr, heatmap_bgr, overlay_bgr, rows, status))
        except Exception:
            error = traceback.format_exc()
            self.root.after(0, lambda: self._show_error(error))

    def _apply_results(self, orig_bgr, det_bgr, heatmap_bgr, overlay_bgr, rows, status):
        self.set_image("Original", orig_bgr)
        self.set_image("Detections", det_bgr)
        self.set_image("Grad-CAM Heatmap", heatmap_bgr)
        self.set_image("Overlay", overlay_bgr)
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            idx, name, prob, x1, y1, x2, y2 = row
            self.tree.insert("", tk.END, values=(idx, name, f"{prob:.3f}", f"{x1},{y1},{x2},{y2}"))
        self.status_var.set(status)

    def _show_error(self, error: str):
        self.status_var.set("Error during inference")
        messagebox.showerror("Inference error", error)

    def set_image(self, title: str, image_bgr: np.ndarray):
        photo = bgr_to_photo(image_bgr, 640, 360)
        self.photos[title] = photo
        self.image_labels[title].configure(image=photo)


def parse_args():
    parser = argparse.ArgumentParser(description="Interactive SSD detection + Grad-CAM UI")
    parser.add_argument("--net", default="mb1-ssd")
    parser.add_argument("--model", default="")
    parser.add_argument("--labels", default="")
    parser.add_argument("--image", default="")
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--target-layer", default="")
    parser.add_argument("--cam-mode", default="auto", choices=["auto", "relu", "signed", "abs"])
    parser.add_argument("--alpha", type=float, default=0.45)
    parser.add_argument("--cpu", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    root = tk.Tk()
    app = SSDGradCamApp(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()
