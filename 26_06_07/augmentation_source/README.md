# Augmentation Source

`object2_colab_augmented` 데이터셋을 만들 때 사용한 증강 생성 코드다.

## 포함

```text
build_augmented_voc_dataset.py
```

## 사용 예

```cmd
python build_augmented_voc_dataset.py object2 object2_colab_augmented
```

입력 `object2`는 VOC 형식이어야 한다.

```text
Annotations/
JPEGImages/
ImageSets/
labels.txt
```

출력 `object2_colab_augmented`는 Colab 학습용으로 압축해 `object2_colab_augmented.zip`으로 사용한다.
