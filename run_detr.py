import torch
from transformers import pipeline
from PIL import Image, ImageDraw, ImageFont

# 1. Load object detection pipeline
print("Loading lightweight DETR model (facebook/detr-resnet-50)...")
device = 0 if torch.cuda.is_available() else -1
detector = pipeline("object-detection", model="facebook/detr-resnet-50", device=device)

# 2. Run detector on image
image_path = "my_photo.png"
print(f"Running detection on {image_path}...")
image = Image.open(image_path).convert("RGB")
results = detector(image)

# 3. Print results and draw boxes
print("\nDetection Results:")
draw = ImageDraw.Draw(image)

# Try loading a clear font for the bounding box text
try:
    font = ImageFont.truetype("arial.ttf", 24)
except IOError:
    font = ImageFont.load_default()

detected_count = 0
for i, result in enumerate(results):
    label = result['label']
    score = result['score']
    box = result['box']
    
    # Only keep detections with high confidence (> 0.7)
    if score < 0.7:
        continue
    
    detected_count += 1
    print(f" - {label} (confidence: {score:.2f}) at coordinates: [xmin: {box['xmin']}, ymin: {box['ymin']}, xmax: {box['xmax']}, ymax: {box['ymax']}]")
    
    # Extract box coordinates
    xmin, ymin, xmax, ymax = box['xmin'], box['ymin'], box['xmax'], box['ymax']
    
    # Draw outline box on image
    draw.rectangle([xmin, ymin, xmax, ymax], outline="#FF0000", width=4)
    
    # Text label background
    text = f"{label} ({score:.2f})"
    try:
        text_w, text_h = draw.textbbox((0, 0), text, font=font)[2:]
    except AttributeError:
        # Fallback for older Pillow versions
        text_w, text_h = 100, 25
        
    draw.rectangle([xmin, ymin - text_h - 4, xmin + text_w + 6, ymin], fill="#FF0000")
    draw.text((xmin + 3, ymin - text_h - 2), text, fill="#FFFFFF", font=font)

# 5. Save the annotated image
output_path = "my_photo_detected.png"
image.save(output_path)
print(f"\nSaved annotated image to {output_path} with {detected_count} object(s) detected.")
