import cv2
import os
import shutil
import xml.etree.ElementTree as ET

IMAGE_DIR = "images"
XML_DIR = "Annotations"

OUT_IMAGE_DIR = "aug_images"
OUT_XML_DIR = "aug_annotations"

os.makedirs(OUT_IMAGE_DIR, exist_ok=True)
os.makedirs(OUT_XML_DIR, exist_ok=True)


def copy_xml(src_xml, dst_xml, new_image_name):
    tree = ET.parse(src_xml)
    root = tree.getroot()

    filename_tag = root.find("filename")
    if filename_tag is not None:
        filename_tag.text = new_image_name

    tree.write(dst_xml, encoding="utf-8")


for filename in os.listdir(IMAGE_DIR):

    if not filename.lower().endswith(".jpg"):
        continue

    name = os.path.splitext(filename)[0]

    img_path = os.path.join(IMAGE_DIR, filename)
    xml_path = os.path.join(XML_DIR, f"{name}.xml")

    if not os.path.exists(xml_path):
        print(f"XML 없음 : {filename}")
        continue

    img = cv2.imread(img_path)

    augments = {
        "bright": cv2.convertScaleAbs(img, alpha=1.0, beta=50),
        "dark": cv2.convertScaleAbs(img, alpha=1.0, beta=-50),
        "contrast_high": cv2.convertScaleAbs(img, alpha=1.5, beta=0),
        "contrast_low": cv2.convertScaleAbs(img, alpha=0.7, beta=0)
    }

    for suffix, aug_img in augments.items():

        new_img_name = f"{name}_{suffix}.jpg"
        new_xml_name = f"{name}_{suffix}.xml"

        cv2.imwrite(
            os.path.join(OUT_IMAGE_DIR, new_img_name),
            aug_img
        )

        copy_xml(
            xml_path,
            os.path.join(OUT_XML_DIR, new_xml_name),
            new_img_name
        )

print("완료")
