# MobileNetV1-SSD Model Reference For Future ONNX Conversion

This file records the concrete model facts from the current conversion.
It intentionally does not include generic ONNX export instructions.

Use this as the comparison sheet when a new checkpoint is trained, labels are added, or ONNX conversion fails.

## Code Provenance

User-provided reference repo for this training session:

- https://github.com/HisameOgasahara/ros_temp/tree/main/26_06_07

Relevant user-provided paths inside that repo:

- https://github.com/HisameOgasahara/ros_temp/tree/main/26_06_07/training_code
- https://github.com/HisameOgasahara/ros_temp/tree/main/26_06_07/training_code/mbnet/ros
- https://github.com/HisameOgasahara/ros_temp/blob/main/26_06_07/colab_object2_train.ipynb

The repo README says this bundle assumes the existing MobileNetV1-SSD training code is provided separately.
The `.pth` converted here matches that MobileNetV1-SSD / `pytorch-ssd` model family.

Upstream implementation family for the model definition and ONNX export style:

- https://github.com/dusty-nv/pytorch-ssd
- https://github.com/dusty-nv/jetson-inference/tree/master/python/training/detection

The checkpoint matches the `pytorch-ssd` MobileNetV1-SSD state dict style:

```text
network name: mb1-ssd
architecture: MobileNetV1-SSD
factory: create_mobilenetv1_ssd(num_classes, is_test=True)
checkpoint type: PyTorch state_dict / OrderedDict
main state_dict key prefixes:
  base_net.*
  source_layer_add_ons.*
  extras.*
  classification_headers.*
  regression_headers.*
```

## Image / Input Contract

The converted model is fixed to this image size:

```text
input image size: 300 x 300
input tensor layout: NCHW
input tensor shape: [1, 3, 300, 300]
input dtype: float32
ONNX input name: input_0
```

The SSD config used here has fixed `image_size = 300`.
The local config did not support arbitrary image size changes through `set_image_size()`.

## SSD Prior / Detection Geometry

Current SSD prior count:

```text
priors shape: [3000, 4]
num priors: 3000
box coordinates per prior: 4
```

Feature map configuration observed from `mobilenetv1_ssd_config`:

```text
feature map 19 x 19, shrinkage 16,  box sizes 60-105,  aspect ratios [2, 3]
feature map 10 x 10, shrinkage 32,  box sizes 105-150, aspect ratios [2, 3]
feature map 5 x 5,   shrinkage 64,  box sizes 150-195, aspect ratios [2, 3]
feature map 3 x 3,   shrinkage 100, box sizes 195-240, aspect ratios [2, 3]
feature map 2 x 2,   shrinkage 150, box sizes 240-285, aspect ratios [2, 3]
feature map 1 x 1,   shrinkage 300, box sizes 285-330, aspect ratios [2, 3]
```

Per feature-map location this model uses 6 anchors.

## Labels Used In This Conversion

The checkpoint was not a 4-class network. It was a 5-class network including background.

Labels actually matching the checkpoint:

```text
0: BACKGROUND
1: Pen
2: Driver
3: Block
4: Wrench
```

The separate 4-line file below existed, but it does not match the checkpoint head by itself:

```text
Pen
Driver
Block
Wrench
```

For this code/model family, future labels should be counted like this:

```text
total_classes = 1 BACKGROUND + object_class_count
```

If labels are added later, the `scores` tensor and classification heads should grow with `total_classes`.

## Current Checkpoint Structure

Checkpoint converted:

```text
mb1-ssd-Epoch-20-Loss-2.7444447619574412.pth
```

Observed checkpoint object:

```text
type: collections.OrderedDict
state_dict key count: 202
```

Classification header weights:

```text
classification_headers.0.weight: [30, 512, 3, 3]
classification_headers.1.weight: [30, 1024, 3, 3]
classification_headers.2.weight: [30, 512, 3, 3]
classification_headers.3.weight: [30, 256, 3, 3]
classification_headers.4.weight: [30, 256, 3, 3]
classification_headers.5.weight: [30, 256, 3, 3]
```

Regression header weights:

```text
regression_headers.0.weight: [24, 512, 3, 3]
regression_headers.1.weight: [24, 1024, 3, 3]
regression_headers.2.weight: [24, 512, 3, 3]
regression_headers.3.weight: [24, 256, 3, 3]
regression_headers.4.weight: [24, 256, 3, 3]
regression_headers.5.weight: [24, 256, 3, 3]
```

Shape meaning:

```text
classification out channels = anchors_per_location * total_classes
30 = 6 * 5

regression out channels = anchors_per_location * box_coordinates
24 = 6 * 4
```

Comparison rule for future checkpoints:

```text
expected classification header out_channels = 6 * total_classes
expected regression header out_channels = 24
```

Examples:

```text
BACKGROUND + 4 object classes = 5 total classes -> classification out_channels 30
BACKGROUND + 5 object classes = 6 total classes -> classification out_channels 36
BACKGROUND + 6 object classes = 7 total classes -> classification out_channels 42
```

If a future checkpoint has a different number in `classification_headers.*.weight[0]`, the labels file must change to match that class count.

## ONNX Model Produced Here

Generated ONNX:

```text
ssd-mobilenet.onnx
```

Observed ONNX metadata:

```text
ir_version: 6
opset: 11
node count: 158
initializer count: 94
external data file: none
```

ONNX input:

```text
name: input_0
dtype: float32
shape: [1, 3, 300, 300]
```

ONNX outputs:

```text
name: scores
dtype: float32
shape: [1, 3000, 5]

name: boxes
dtype: float32
shape: [1, 3000, 4]
```

Output shape meaning:

```text
scores[batch, prior_index, class_index]
boxes[batch, prior_index, box_coordinate]
```

For future checkpoints with added labels:

```text
scores shape: [1, 3000, total_classes]
boxes shape: [1, 3000, 4]
```

The second dimension should stay `3000` as long as the same 300x300 MobileNetV1-SSD prior config is used.

## Jetson-Inference Blob Names

The ONNX graph produced here expects these blob names for `detectnet` / `jetson-inference`:

```text
input blob: input_0
coverage/class scores output: scores
bounding box output: boxes
```

These names are part of the concrete ONNX graph produced here.

## Practical Mismatch Clues

If a future export fails while loading the checkpoint:

```text
Check classification_headers.*.weight first dimension.
Compare it with 6 * total label lines including BACKGROUND.
```

If inference loads but class results are shifted or wrong:

```text
Check whether BACKGROUND is present as label index 0.
Check whether label order matches the training class order.
```

If ONNX output shape differs:

```text
scores last dimension should equal total_classes.
boxes last dimension should remain 4.
prior dimension should remain 3000 for this exact SSD config.
```
