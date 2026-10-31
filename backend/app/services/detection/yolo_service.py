"""
app/yolo_service.py — Shared YOLO object detector service with thread-safe inference.
Reuses the single loaded model instance across multiple sessions for memory efficiency.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional
import numpy as np
import torch

import backend.app.core.config as config


class YOLOService:
    """Singleton service providing thread-safe YOLO object detection."""

    _instance: Optional[YOLOService] = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() and config.DEVICE in ("auto", "cuda") else "cpu"
        self._lock = threading.Lock()
        self.model = None
        self._load_model()

    @classmethod
    def get_instance(cls) -> YOLOService:
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO
            if os.path.isfile(config.YOLO_WEIGHTS):
                self.model = YOLO(config.YOLO_WEIGHTS)
                self.model.to(self.device)
                print(f"[YOLOService] Loaded YOLOv8 from '{config.YOLO_WEIGHTS}' on {self.device.upper()}")
            else:
                print(f"[YOLOService] Warning: Weights file '{config.YOLO_WEIGHTS}' not found.")
        except Exception as e:
            print(f"[YOLOService] Warning: Could not initialize YOLO: {e}")
            self.model = None

    def detect(self, bgr_frame: np.ndarray) -> Dict[str, Any]:
        """
        Thread-safe detection for person, cell phone, book, laptop.
        """
        result_info = {
            "person_detected": False,
            "person_conf": 0.0,
            "person_box": None,
            "phone_detected": False,
            "phone_conf": 0.0,
            "phone_box": None,
            "book_detected": False,
            "book_conf": 0.0,
            "book_box": None,
            "laptop_detected": False,
            "laptop_conf": 0.0,
            "laptop_box": None,
        }

        if self.model is None or bgr_frame is None:
            return result_info

        try:
            with self._lock:
                preds = self.model(
                    bgr_frame,
                    classes=[
                        config.COCO_PERSON,
                        config.COCO_CELL_PHONE,
                        config.COCO_BOOK,
                        config.COCO_LAPTOP,
                    ],
                    conf=config.YOLO_CONF_THRESHOLD,
                    iou=config.YOLO_IOU_THRESHOLD,
                    verbose=False,
                )

            if preds and len(preds) > 0 and preds[0].boxes is not None:
                boxes = preds[0].boxes
                h, w = bgr_frame.shape[:2]
                max_person_area = 0.0

                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    coords = [int(v) for v in box.xyxy[0].tolist()]

                    if cls_id == config.COCO_PERSON and conf >= getattr(config, "YOLO_CONF_PERSON", 0.40):
                        area = (coords[2] - coords[0]) * (coords[3] - coords[1])
                        if area > max_person_area:
                            max_person_area = area
                            result_info["person_detected"] = True
                            result_info["person_conf"] = conf
                            result_info["person_box"] = coords

                    elif cls_id == config.COCO_CELL_PHONE and conf >= getattr(config, "YOLO_CONF_PHONE", 0.28):
                        result_info["phone_detected"] = True
                        result_info["phone_conf"] = conf
                        result_info["phone_box"] = coords

                    elif cls_id == config.COCO_BOOK and conf >= getattr(config, "YOLO_CONF_BOOK", 0.35):
                        result_info["book_detected"] = True
                        result_info["book_conf"] = conf
                        result_info["book_box"] = coords

                    elif cls_id == config.COCO_LAPTOP and conf >= getattr(config, "YOLO_CONF_LAPTOP", 0.38):
                        result_info["laptop_detected"] = True
                        result_info["laptop_conf"] = conf
                        result_info["laptop_box"] = coords

        except Exception as e:
            print(f"[YOLOService] Inference error: {e}")

        return result_info

