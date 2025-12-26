import yaml
import threading
import os

class ConfigManager:
    def __init__(self, yaml_path="configs/configs.yaml"):
        self.yaml_path = yaml_path
        self.lock = threading.Lock()
        self.config = {}
        try:
            self.load()
        except Exception:
            self.config = {}
        
        with self.lock:
            self.config.setdefault("crop_enabled", False)
            self.config.setdefault("crop_x", 0)
            self.config.setdefault("crop_y", 0)
            self.config.setdefault("crop_w", 640)
            self.config.setdefault("crop_h", 480)
            self.config.setdefault("conf_threshold", 0.3)
            self.config.setdefault("drowsy_time_threshold", 2.0)
            self.config.setdefault("frame_rate", 30)
            self.config.setdefault("led_pin", 21)
            self.config.setdefault("yolo_path", "weights/new-best.onnx")
            self.config.setdefault("eye_model_path", "weights/eye_model.onnx")
            self.config.setdefault("yolo_img_size", 224)
            self.config.setdefault("iou_threshold", 0.35)
            self.config.setdefault("eye_img_size", 128)

    def load(self):
        if not os.path.exists(self.yaml_path):
            self.config = {}
            return
        with open(self.yaml_path, "r") as f:
            self.config = yaml.safe_load(f) or {}

    def get(self, key, default=None):
        with self.lock:
            return self.config.get(key, default)

    def set(self, key, value):
        with self.lock:
            self.config[key] = value

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.yaml_path), exist_ok=True)
            with open(self.yaml_path, "w") as f:
                yaml.safe_dump(self.config, f)

    def snapshot(self):
        with self.lock:
            return dict(self.config)