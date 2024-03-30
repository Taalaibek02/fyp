import numpy as np
import cv2


# Initialize a dictionary to hold the results
event_results = {}

# Define the event name or ID somehow, maybe it's based on the image name or it's provided externally
event_name = "event_identifier"  # Replace with the actual identifier for the event

# Load the cascades
faceCascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
smileCascade = cv2.CascadeClassifier('haarcascade_smile.xml')

# Load an image from file
image_path = 'R3.jpeg'  # Replace with your image path
img = cv2.imread(image_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Detect faces in the image
faces = faceCascade.detectMultiScale(
    gray,
    scaleFactor=1.3,
    minNeighbors=5,
    minSize=(30, 30)
)

total_faces = len(faces)
smiling_faces = 0

# Draw rectangles around the faces and look for smiles
for (x, y, w, h) in faces:
    cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
    roi_gray = gray[y:y + h, x:x + w]

    # Detect smiles within the face ROI
    smile = smileCascade.detectMultiScale(
        roi_gray,
        scaleFactor=1.7,
        minNeighbors=20,
        minSize=(25, 25),
    )

    # If smiles are detected, mark the person as smiling
    for i in smile:
        if len(smile) > 1:
            smiling_faces += 1
            cv2.putText(img, "Smiling", (x, y - 30), cv2.FONT_HERSHEY_SIMPLEX,
                        2, (0, 0, 255), 3, cv2.LINE_AA)
            

# Calculate the smile ratio
smile_ratio = smiling_faces / total_faces if total_faces > 0 else 0

# Store the results in the dictionary
event_results[event_name] = {
    'image_path': image_path,
    'total_faces': total_faces,
    'smiling_faces': smiling_faces,
    'smile_ratio': smile_ratio
}

print(event_results)

# Optionally, save the event_results dictionary to a file using a library like json or pickle
import json
with open('event_results.json', 'w') as fp:
    json.dump(event_results, fp, indent=4)

# Show the output image
cv2.imshow('Smile Detection', img)
cv2.waitKey(0)  # Wait indefinitely until a key is pressed
cv2.destroyAllWindows()