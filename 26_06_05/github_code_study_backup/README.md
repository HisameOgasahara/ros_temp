# SSD / ROS Code Study Backup

This folder is a code-only backup for studying the SSD training, inference,
Grad-CAM, dataset conversion, and camera-capture UI code.

It intentionally excludes:

- Open Images / VOC converted datasets
- downloaded annotation CSV files
- trained model weights and checkpoints
- test images, generated heatmaps, and overlays
- local virtual environments and cache files

Main areas:

- `mbnet/ros`: training scripts, Open Images downloader, Open Images-to-VOC converter,
  Grad-CAM scripts, and the standalone SSD Grad-CAM UI.
- `mbnet/camera-capture`: C++/Qt camera capture and manual labeling UI source.
- `pytorch-ssd/vision`: SSD model, dataset, transform, loss, and utility source code
  needed by the training/inference scripts.

Useful local commands from the original workspace:

```bat
mbnet\ros\start_training.cmd
mbnet\ros\start_gradcam_ui.cmd
```

Those commands prefer a local `venv` or `.venv`, but fall back to `python` on PATH.
Install dependencies first:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Training still requires a VOC-style dataset and a pretrained `.pth` file, which
are intentionally not included. Pass them explicitly:

```bat
mbnet\ros\start_training.cmd path\to\voc_dataset path\to\pretrained.pth
```

The Grad-CAM UI starts without bundled weights. Use the UI's Browse button to
select a trained `.pth` model. The default labels file is `mbnet\ros\labels.txt`.
