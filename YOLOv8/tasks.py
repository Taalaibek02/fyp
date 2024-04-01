from ultralytics import YOLO
from PIL import Image
import cv2
import torch
import numpy as np 
import os
from pathlib import Path

photo_path = os.path.join('..','dataset','bicycle', 'guitar.jpeg')
im2 = cv2.imread('smile_detection-master/R3.jpeg')

model_paths = [
    os.path.join('.','YOLOv8','runs','detect','train16','weights','best.pt'),
    os.path.join('.','YOLOv8','runs','detect','train15','weights','best.pt'),
    os.path.join('.','YOLOv8','runs','detect','train14','weights','best.pt')
]

models = [YOLO(path) for path in model_paths]

results = {}

for i, model in enumerate(models):
    print(model.model_name)
    result = model(source=im2, conf=0.6, save=True)

    all_class_ids = []
    for r in result:

        all_class_ids.extend(r.boxes.cls.tolist())



    detected_tags = [model.names[int(cls_id)] for cls_id in all_class_ids]

    results[f'model_{i+1}'] = detected_tags

output_filename = os.path.splitext(os.path.basename(photo_path))[0] + "_tags.txt"
output_path = os.path.join('detected_tags', output_filename)

os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, 'w') as file:
    for model_name, tags in results.items():
        # Ensure tags are all strings
        tags_str = [str(tag) for tag in tags]
        file.write(f"{model_name}: {', '.join(tags_str)}\n")

print(f"Detected tags saved to {output_path}")
print(results)
print(results.items())
