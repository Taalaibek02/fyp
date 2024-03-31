import json
import os
import cv2
from ultralytics import YOLO

# Define the event name or ID somehow, maybe it's based on the image name or it's provided externally
event_name = "event_identifier"  # Replace with the actual identifier for the event

# Define the path to your image
image_path = 'smile_detection-master/R3.jpeg'  # Replace with your image path

# Initialize a dictionary to hold the results
event_results = {}

# Load the cascades for smile detection
faceCascade = cv2.CascadeClassifier('smile_detection-master/haarcascade_frontalface_default.xml')
smileCascade = cv2.CascadeClassifier('smile_detection-master/haarcascade_smile.xml')

# Load an image from file
img = cv2.imread(image_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Detect faces in the image
faces = faceCascade.detectMultiScale(
    gray,
    scaleFactor=1.3,
    minNeighbors=5,
    minSize=(30, 30)
)

# Smile detection
total_faces = len(faces)
smiling_faces = 0

# Detect smiles within the faces
for (x, y, w, h) in faces:
    roi_gray = gray[y:y + h, x:x + w]
    smile = smileCascade.detectMultiScale(
        roi_gray,
        scaleFactor=1.7,
        minNeighbors=20,
        minSize=(25, 25),
    )
    if len(smile) > 1:
        smiling_faces += 1

# Calculate the smile ratio
smile_ratio = smiling_faces / total_faces if total_faces > 0 else 0

# Object detection
model_paths = [
    'YOLOv8/runs/detect/train16/weights/best.pt',
    'YOLOv8/runs/detect/train15/weights/best.pt',
    'YOLOv8/runs/detect/train14/weights/best.pt'
]

# Initialize YOLO models
models = [YOLO(path) for path in model_paths]

detected_objects = []

# Run object detection for each model
for model in models:
    result = model(img, size=640)
    for r in result:
        detected_objects.extend(r.boxes.cls.tolist())  # Extract class IDs

# Convert class IDs to names
object_tags = [model.names[int(cls_id)] for cls_id in set(detected_objects)]

# Store the combined results in the dictionary
event_results[event_name] = {
    'image_path': image_path,
    'total_faces': total_faces,
    'smiling_faces': smiling_faces,
    'smile_ratio': smile_ratio,
    'detected_objects': object_tags
}

# Save the combined results to a JSON file
with open('event_results.json', 'w') as fp:
    json.dump(event_results, fp, indent=4)

# Show the output image with smile detection
cv2.imshow('Smile Detection', img)
cv2.waitKey(0)  # Wait indefinitely until a key is pressed
cv2.destroyAllWindows()

# Output the combined results
print(event_results)