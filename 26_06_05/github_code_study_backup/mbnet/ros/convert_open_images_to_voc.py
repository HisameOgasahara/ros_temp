#!/usr/bin/env python3
import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert this project's Open Images CSV layout to Pascal VOC layout."
    )
    parser.add_argument("--src", required=True, help="Open Images dataset root")
    parser.add_argument("--dst", required=True, help="Output VOC dataset root")
    parser.add_argument(
        "--splits",
        default="train,validation,test",
        help="Comma-separated source splits to convert",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy image files instead of hard-linking them",
    )
    return parser.parse_args()


def indent_xml(element, level=0):
    indent = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        for child in element:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indent


def add_text(parent, name, value):
    child = ET.SubElement(parent, name)
    child.text = str(value)
    return child


def read_labels(src):
    label_file = src / "labels.txt"
    if not label_file.exists():
        return None
    labels = []
    for line in label_file.read_text().splitlines():
        label = line.strip()
        if label and label.upper() != "BACKGROUND":
            labels.append(label.lower())
    return labels


def link_or_copy(src_file, dst_file, copy):
    if dst_file.exists():
        return
    if copy:
        shutil.copy2(src_file, dst_file)
        return
    try:
        dst_file.hardlink_to(src_file)
    except OSError:
        shutil.copy2(src_file, dst_file)


def make_annotation(dataset_name, image_filename, image_shape, rows, labels):
    height, width = image_shape[:2]
    root = ET.Element("annotation")
    add_text(root, "folder", dataset_name)
    add_text(root, "filename", image_filename)

    source = ET.SubElement(root, "source")
    add_text(source, "database", dataset_name)
    add_text(source, "annotation", "open_images")
    add_text(source, "image", "open_images")

    size = ET.SubElement(root, "size")
    add_text(size, "width", width)
    add_text(size, "height", height)
    add_text(size, "depth", 3)
    add_text(root, "segmented", 0)

    for row in rows.itertuples(index=False):
        class_name = str(row.ClassName).lower()
        if labels is not None and class_name not in labels:
            continue

        xmin = max(1, min(width, int(round(float(row.XMin) * width)) + 1))
        ymin = max(1, min(height, int(round(float(row.YMin) * height)) + 1))
        xmax = max(1, min(width, int(round(float(row.XMax) * width))))
        ymax = max(1, min(height, int(round(float(row.YMax) * height))))

        if xmax <= xmin or ymax <= ymin:
            continue

        obj = ET.SubElement(root, "object")
        add_text(obj, "name", class_name)
        add_text(obj, "pose", "unspecified")
        add_text(obj, "truncated", int(getattr(row, "IsTruncated", 0)))
        add_text(obj, "difficult", 0)

        box = ET.SubElement(obj, "bndbox")
        add_text(box, "xmin", xmin)
        add_text(box, "ymin", ymin)
        add_text(box, "xmax", xmax)
        add_text(box, "ymax", ymax)

    indent_xml(root)
    return ET.ElementTree(root), len(root.findall("object"))


def main():
    args = parse_args()
    src = Path(args.src)
    dst = Path(args.dst)
    splits = [split.strip() for split in args.splits.split(",") if split.strip()]
    labels = read_labels(src)

    annotations_dir = dst / "Annotations"
    images_dir = dst / "JPEGImages"
    image_sets_dir = dst / "ImageSets" / "Main"
    annotations_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    image_sets_dir.mkdir(parents=True, exist_ok=True)

    if labels:
        (dst / "labels.txt").write_text(",".join(labels) + "\n")

    trainval_ids = []
    test_ids = []
    converted = 0
    skipped = 0

    for split in splits:
        csv_file = src / f"sub-{split}-annotations-bbox.csv"
        image_dir = src / split
        if not csv_file.exists():
            print(f"skip missing annotations: {csv_file}")
            continue

        annotations = pd.read_csv(csv_file)
        split_ids = []

        for image_id, rows in annotations.groupby("ImageID"):
            source_image = image_dir / f"{image_id}.jpg"
            if not source_image.exists():
                skipped += 1
                continue

            image = cv2.imread(str(source_image))
            if image is None:
                skipped += 1
                continue

            voc_id = f"{split}_{image_id}"
            voc_image_name = f"{voc_id}.jpg"
            xml_tree, object_count = make_annotation(
                dst.name, voc_image_name, image.shape, rows, labels
            )
            if object_count == 0:
                skipped += 1
                continue

            link_or_copy(source_image, images_dir / voc_image_name, args.copy)
            xml_tree.write(annotations_dir / f"{voc_id}.xml", encoding="utf-8", xml_declaration=False)
            split_ids.append(voc_id)
            converted += 1

        (image_sets_dir / f"{split}.txt").write_text("\n".join(split_ids) + "\n")
        if split == "test":
            test_ids.extend(split_ids)
        else:
            trainval_ids.extend(split_ids)

    (image_sets_dir / "trainval.txt").write_text("\n".join(trainval_ids) + "\n")
    (image_sets_dir / "test.txt").write_text("\n".join(test_ids) + "\n")

    print(f"converted images: {converted}")
    print(f"skipped images: {skipped}")
    print(f"output: {dst}")


if __name__ == "__main__":
    main()
