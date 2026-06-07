#!/usr/bin/env python3
import argparse
import random
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


CLASS_NAMES = ["pen", "driver", "block", "wrench"]
LABEL_CASE = {
    "pen": "Pen",
    "driver": "Driver",
    "block": "Block",
    "wrench": "Wrench",
}
IMAGE_SIZE = (1280, 720)
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
RANDOM_SEED = 260608


def clamp_box(box, width, height):
    xmin, ymin, xmax, ymax = [int(round(v)) for v in box]
    xmin = max(1, min(width, xmin))
    ymin = max(1, min(height, ymin))
    xmax = max(1, min(width, xmax))
    ymax = max(1, min(height, ymax))
    if xmax <= xmin:
        xmax = min(width, xmin + 1)
        xmin = max(1, xmax - 1)
    if ymax <= ymin:
        ymax = min(height, ymin + 1)
        ymin = max(1, ymax - 1)
    return [xmin, ymin, xmax, ymax]


def horizontal_flip_box(box, width):
    xmin, ymin, xmax, ymax = box
    return [width - xmax + 1, ymin, width - xmin + 1, ymax]


def translate_box(box, dx, dy, width, height):
    xmin, ymin, xmax, ymax = box
    return clamp_box([xmin + dx, ymin + dy, xmax + dx, ymax + dy], width, height)


def zoom_out_box(box, width, height, scale):
    x_offset = (width - width * scale) / 2
    y_offset = (height - height * scale) / 2
    xmin, ymin, xmax, ymax = box
    return clamp_box(
        [
            xmin * scale + x_offset,
            ymin * scale + y_offset,
            xmax * scale + x_offset,
            ymax * scale + y_offset,
        ],
        width,
        height,
    )


def read_ids(source_root):
    trainval = source_root / "ImageSets" / "Main" / "trainval.txt"
    if trainval.is_file():
        return [line.strip() for line in trainval.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return sorted(path.stem for path in (source_root / "Annotations").glob("*.xml"))


def read_record(source_root, image_id):
    xml_path = source_root / "Annotations" / f"{image_id}.xml"
    tree = ET.parse(xml_path)
    root = tree.getroot()
    width = int(root.findtext("size/width"))
    height = int(root.findtext("size/height"))
    objects = []
    for obj in root.findall("object"):
        label = obj.findtext("name", "").strip()
        label_key = label.lower()
        if label_key not in CLASS_NAMES:
            continue
        box_node = obj.find("bndbox")
        box = [
            int(float(box_node.findtext("xmin"))),
            int(float(box_node.findtext("ymin"))),
            int(float(box_node.findtext("xmax"))),
            int(float(box_node.findtext("ymax"))),
        ]
        objects.append((LABEL_CASE[label_key], clamp_box(box, width, height)))
    return width, height, objects


def make_annotation(image_id, width, height, objects):
    root = ET.Element("annotation")
    ET.SubElement(root, "filename").text = f"{image_id}.jpg"
    ET.SubElement(root, "folder").text = "object2_colab_augmented"
    source = ET.SubElement(root, "source")
    ET.SubElement(source, "database").text = "object2_colab_augmented"
    ET.SubElement(source, "annotation").text = "custom"
    ET.SubElement(source, "image").text = "custom"
    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(width)
    ET.SubElement(size, "height").text = str(height)
    ET.SubElement(size, "depth").text = "3"
    ET.SubElement(root, "segmented").text = "0"
    for label, box in objects:
        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = label
        ET.SubElement(obj, "pose").text = "unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"
        bndbox = ET.SubElement(obj, "bndbox")
        for tag, value in zip(("xmin", "ymin", "xmax", "ymax"), box):
            ET.SubElement(bndbox, tag).text = str(value)
    return ET.ElementTree(root)


def save_item(output_root, image_id, image, width, height, objects):
    image.save(output_root / "JPEGImages" / f"{image_id}.jpg", quality=95)
    make_annotation(image_id, width, height, objects).write(
        output_root / "Annotations" / f"{image_id}.xml",
        encoding="utf-8",
        xml_declaration=False,
    )


def apply_photometric(image):
    return {
        "bright": ImageEnhance.Brightness(image).enhance(1.25),
        "dark": ImageEnhance.Brightness(image).enhance(0.75),
        "contrast_high": ImageEnhance.Contrast(image).enhance(1.35),
        "contrast_low": ImageEnhance.Contrast(image).enhance(0.75),
        "gamma_light": image.point(lambda p: int(255 * ((p / 255) ** 0.8))),
        "gamma_dark": image.point(lambda p: int(255 * ((p / 255) ** 1.25))),
        "saturation_up": ImageEnhance.Color(image).enhance(1.35),
        "saturation_down": ImageEnhance.Color(image).enhance(0.65),
        "warm_color": color_temperature(image, red_scale=1.08, blue_scale=0.92),
        "cool_color": color_temperature(image, red_scale=0.92, blue_scale=1.08),
    }


def color_temperature(image, red_scale, blue_scale):
    r, g, b = image.split()
    r = r.point(lambda p: max(0, min(255, int(p * red_scale))))
    b = b.point(lambda p: max(0, min(255, int(p * blue_scale))))
    return Image.merge("RGB", (r, g, b))


def apply_geometric(image, width, height, objects):
    dx = int(width * 0.05)
    dy = int(height * 0.05)
    gray = (128, 128, 128)
    variants = {}

    flipped = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    variants["hflip"] = (flipped, [(label, horizontal_flip_box(box, width)) for label, box in objects])

    for name, shift_x, shift_y in (
        ("translate_left", -dx, 0),
        ("translate_right", dx, 0),
        ("translate_up", 0, -dy),
        ("translate_down", 0, dy),
    ):
        canvas = Image.new("RGB", (width, height), gray)
        canvas.paste(image, (shift_x, shift_y))
        variants[name] = (
            canvas,
            [(label, translate_box(box, shift_x, shift_y, width, height)) for label, box in objects],
        )

    scale = 0.9
    scaled = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), gray)
    offset = ((width - scaled.width) // 2, (height - scaled.height) // 2)
    canvas.paste(scaled, offset)
    variants["zoom_out"] = (
        canvas,
        [(label, zoom_out_box(box, width, height, scale)) for label, box in objects],
    )

    return variants


def split_ids(ids):
    ids = sorted(ids)
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(ids)
    total = len(ids)
    train_end = int(total * TRAIN_RATIO)
    val_end = train_end + int(total * VAL_RATIO)
    return {
        "train": sorted(ids[:train_end]),
        "val": sorted(ids[train_end:val_end]),
        "test": sorted(ids[val_end:]),
    }


def write_split_files(output_root, split_map, generated_by_parent):
    main = output_root / "ImageSets" / "Main"
    for split_name, parent_ids in split_map.items():
        image_ids = []
        for parent_id in parent_ids:
            image_ids.extend(generated_by_parent[parent_id])
        (main / f"{split_name}.txt").write_text("\n".join(image_ids) + "\n", encoding="utf-8")

    trainval = []
    for split_name in ("train", "val"):
        trainval.extend((main / f"{split_name}.txt").read_text(encoding="utf-8").splitlines())
    (main / "trainval.txt").write_text("\n".join([line for line in trainval if line]) + "\n", encoding="utf-8")


def build_dataset(source_root, output_root):
    source_root = Path(source_root)
    output_root = Path(output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    for subdir in ("Annotations", "JPEGImages", "ImageSets/Main"):
        (output_root / subdir).mkdir(parents=True, exist_ok=True)
    (output_root / "labels.txt").write_text("\n".join([LABEL_CASE[name] for name in CLASS_NAMES]) + "\n", encoding="utf-8")

    parent_ids = read_ids(source_root)
    split_map = split_ids(parent_ids)
    generated_by_parent = {}
    counts = Counter()

    for parent_id in parent_ids:
        width, height, objects = read_record(source_root, parent_id)
        if (width, height) != IMAGE_SIZE:
            raise ValueError(f"Unexpected image size for {parent_id}: {(width, height)}")
        if not objects:
            continue

        image = Image.open(source_root / "JPEGImages" / f"{parent_id}.jpg").convert("RGB")
        generated_ids = []

        original_id = f"{parent_id}_orig"
        save_item(output_root, original_id, image, width, height, objects)
        generated_ids.append(original_id)
        for label, _box in objects:
            counts[label.lower()] += 1

        for suffix, aug_image in apply_photometric(image).items():
            image_id = f"{parent_id}_{suffix}"
            save_item(output_root, image_id, aug_image, width, height, objects)
            generated_ids.append(image_id)
            for label, _box in objects:
                counts[label.lower()] += 1

        for suffix, (aug_image, aug_objects) in apply_geometric(image, width, height, objects).items():
            image_id = f"{parent_id}_{suffix}"
            save_item(output_root, image_id, aug_image, width, height, aug_objects)
            generated_ids.append(image_id)
            for label, _box in aug_objects:
                counts[label.lower()] += 1

        generated_by_parent[parent_id] = generated_ids

    write_split_files(output_root, split_map, generated_by_parent)
    return {
        "source_count": len(parent_ids),
        "image_count": sum(len(v) for v in generated_by_parent.values()),
        "class_counts": dict(sorted(counts.items())),
        "split_parent_counts": {name: len(ids) for name, ids in split_map.items()},
    }


def main():
    parser = argparse.ArgumentParser(description="Build a grouped augmented VOC dataset for Colab training.")
    parser.add_argument("--source", default="object2", type=Path)
    parser.add_argument("--output", default="object2_colab_augmented", type=Path)
    args = parser.parse_args()
    summary = build_dataset(args.source, args.output)
    print(f"source_count={summary['source_count']}")
    print(f"image_count={summary['image_count']}")
    print(f"split_parent_counts={summary['split_parent_counts']}")
    print(f"class_counts={summary['class_counts']}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
