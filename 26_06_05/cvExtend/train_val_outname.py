import os
import random

ANNOTATION_DIR = "aug_annotations"
IMAGESET_DIR = "ImageSets/Main"

os.makedirs(IMAGESET_DIR, exist_ok=True)

all_files = []

for file in os.listdir(ANNOTATION_DIR):

    if file.endswith(".xml"):
        all_files.append(
            os.path.splitext(file)[0]
        )

random.shuffle(all_files)

total = len(all_files)

train_ratio = 0.8
val_ratio = 0.1

train_end = int(total * train_ratio)
val_end = train_end + int(total * val_ratio)

train = all_files[:train_end]
val = all_files[train_end:val_end]
test = all_files[val_end:]

trainval = train + val


def save_txt(filename, data):

    with open(
        os.path.join(IMAGESET_DIR, filename),
        "w"
    ) as f:

        for item in data:
            f.write(item + "\n")


save_txt("train.txt", train)
save_txt("val.txt", val)
save_txt("test.txt", test)
save_txt("trainval.txt", trainval)

print("완료")
print(f"train={len(train)}")
print(f"val={len(val)}")
print(f"test={len(test)}")
