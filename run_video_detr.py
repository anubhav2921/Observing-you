import cv2
import torch
import numpy as np
from PIL import Image
from transformers import pipeline

# 1. Load object detection pipeline
print("Loading lightweight DETR model (facebook/detr-resnet-50)...")
device = 0 if torch.cuda.is_available() else -1
detector = pipeline("object-detection", model="facebook/detr-resnet-50", device=device)

def process_video(input_path, output_path):
    # Open the input video file
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {input_path}")
        return
    
    # Extract video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"\nProcessing Video: {input_path}")
    print(f"Resolution: {width}x{height} | FPS: {fps} | Total Frames: {total_frames}")
    
    # Setup video writer to save annotated video
    # Use 'vp09' (VP9) codec for HTML5 and IDE video viewer compatibility
    fourcc = cv2.VideoWriter_fourcc(*'vp09')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break  # End of video
        
        # OpenCV reads in BGR format; convert to RGB for Hugging Face detector
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert numpy frame to PIL Image
        frame_pil = Image.fromarray(frame_rgb)
        
        # Perform object detection
        results = detector(frame_pil)
        
        # Annotate each frame
        for result in results:
            label = result['label']
            score = result['score']
            box = result['box']
            
            # Show objects with confidence higher than 70%
            if score > 0.7:
                xmin = int(box['xmin'])
                ymin = int(box['ymin'])
                xmax = int(box['xmax'])
                ymax = int(box['ymax'])
                
                # Draw bounding box (Red box, width 3)
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 0, 255), 3)
                
                # Draw background rectangle for label text
                text = f"{label} ({score:.2f})"
                (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (xmin, ymin - text_height - 10), (xmin + text_width, ymin), (0, 0, 255), cv2.FILLED)
                
                # Overlay label text (White text)
                cv2.putText(frame, text, (xmin, ymin - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Write the annotated frame to output video
        out.write(frame)
        
        frame_count += 1
        if frame_count % 30 == 0 or frame_count == total_frames:
            print(f"Progress: Processed frame {frame_count}/{total_frames} ({frame_count/total_frames*100:.1f}%)")
            
    # Clean up and release readers/writers
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"\nDone! Annotated video saved successfully to: {output_path}")

if __name__ == "__main__":
    # REPLACE with your own video file names:
    input_file = "Screen Recording 2026-08-11 092900.mp4"       # Input video file name
    output_file = "Screen Recording_detected.mp4" # Output file name to save annotated video
    
    import os
    if not os.path.exists(input_file):
        print(f"Error: '{input_file}' not found in the workspace directory.")
        print("Please place a video file named 'my_video.mp4' in this directory, or change 'input_file' variable inside run_video_detr.py to point to your video file.")
    else:
        process_video(input_file, output_file)
