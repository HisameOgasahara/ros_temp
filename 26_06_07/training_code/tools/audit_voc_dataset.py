#!/usr/bin/env python3
import argparse
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def read_labels(dataset_root):
    label_file = dataset_root / "labels.txt"
    if not label_file.is_file():
        return []
    text = label_file.read_text(encoding="utf-8-sig")
    return [item.strip().lower().replace(" ", "") for item in re.split(r"[,\r\n]+", text) if item.strip()]


def read_ids(path):
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Audit a VOC-style dataset without importing torch or cv2.")
    parser.add_argument("dataset_root", type=Path)
    args = parser.parse_args()

    root = args.dataset_root
    labels = read_labels(root)
    allowed = set(labels)
    class_counts = Counter()
    missing = []
    unknown_labels = []
    bad_boxes = []

    trainval_ids = read_ids(root / "ImageSets" / "Main" / "trainval.txt")
    train_ids = read_ids(root / "ImageSets" / "Main" / "train.txt")
    test_ids = read_ids(root / "ImageSets" / "Main" / "test.txt")

    all_ids = trainval_ids or train_ids
    for image_id in all_ids:
        image_path = root / "JPEGImages" / f"{image_id}.jpg"
        xml_path = root / "Annotations" / f"{image_id}.xml"
        if not image_path.is_file():
            missing.append(f"missing image: {image_path}")
        if not xml_path.is_file():
            missing.append(f"missing annotation: {xml_path}")
            continue

        tree = ET.parse(xml_path)
        annotation = tree.getroot()
        width = int(annotation.findtext("size/width", "0"))
        height = int(annotation.findtext("size/height", "0"))

        for obj in annotation.findall("object"):
            raw_name = obj.findtext("name", "").strip()
            name = raw_name.lower().replace(" ", "")
            class_counts[name] += 1
            if allowed and name not in allowed:
                unknown_labels.append(f"{xml_path.name}: {raw_name}")

            xmin = int(float(obj.findtext("bndbox/xmin", "0")))
            ymin = int(float(obj.findtext("bndbox/ymin", "0")))
            xmax = int(float(obj.findtext("bndbox/xmax", "0")))
            ymax = int(float(obj.findtext("bndbox/ymax", "0")))
            if xmin < 1 or ymin < 1 or xmax <= xmin or ymax <= ymin or xmax > width or ymax > height:
                bad_boxes.append(f"{xml_path.name}: {raw_name} box=({xmin},{ymin},{xmax},{ymax}) image=({width},{height})")

    print(f"dataset_root={root}")
    print(f"labels={labels}")
    print(f"train={len(train_ids)} trainval={len(trainval_ids)} test={len(test_ids)}")
    print("class_counts=" + ", ".join(f"{k}:{v}" for k, v in sorted(class_counts.items())))
    print(f"missing={len(missing)}")
    for item in missing:
        print(f"  {item}")
    print(f"unknown_labels={len(unknown_labels)}")
    for item in unknown_labels:
        print(f"  {item}")
    print(f"bad_boxes={len(bad_boxes)}")
    for item in bad_boxes:
        print(f"  {item}")


if __name__ == "__main__":
    main()
