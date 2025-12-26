# models.py
import cv2
import numpy as np
import onnxruntime as ort
from src.utils import softmax
import os
import time

def save_img_bgr(img_bgr, save_dir="debug_imgs"):
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{int(time.time() * 1000)}.jpg"
    save_path = os.path.join(save_dir, filename)
    cv2.imwrite(save_path, img_bgr)
    return save_path

class YOLOModel:
    def __init__(self, model_path, input_size=224, conf_thres=0.3, iou_thres=0.35):
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 2 
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        self.session = ort.InferenceSession(model_path, sess_options, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres

    def preprocess(self, img_bgr):
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)  
        h, w = img_rgb.shape[:2]
        scale = min(self.input_size / h, self.input_size / w)
        nw, nh = int(w * scale), int(h * scale)
        img_resized = cv2.resize(img_rgb, (nw, nh))
        image_padded = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        dw, dh = (self.input_size - nw) // 2, (self.input_size - nh) // 2
        image_padded[dh:nh+dh, dw:nw+dw] = img_resized
        img_input = image_padded.astype(np.float32) / 255.0
        img_input = img_input.transpose(2, 0, 1)
        img_input = np.expand_dims(img_input, 0)
        return img_input, scale, (dw, dh)

    def detect(self, frame):
        input_tensor, scale, (pad_w, pad_h) = self.preprocess(frame)
        outputs = self.session.run(None, {self.input_name: input_tensor})
        preds = outputs[0][0].transpose()
        boxes_temp, scores_temp = [], []
        for row in preds:
            classes_scores = row[4:]
            max_score = np.amax(classes_scores)
            if max_score >= self.conf_thres:
                cx, cy, w, h = row[:4]
                x = int(cx - w / 2)
                y = int(cy - h / 2)
                boxes_temp.append([x, y, int(w), int(h)])
                scores_temp.append(float(max_score))
        indices = cv2.dnn.NMSBoxes(boxes_temp, scores_temp, self.conf_thres, self.iou_thres)
        final_boxes = []
        if len(indices) > 0:
            frame_h, frame_w = frame.shape[:2]
            for i in indices.flatten():
                bx, by, bw, bh = boxes_temp[i]
                real_x1 = max(0, int((bx - pad_w) / scale))
                real_y1 = max(0, int((by - pad_h) / scale))
                real_x2 = min(frame_w, real_x1 + int(bw / scale))
                real_y2 = min(frame_h, real_y1 + int(bh / scale))
                final_boxes.append([real_x1, real_y1, real_x2, real_y2])
        return final_boxes


class EyeClassifier:
    def __init__(self, model_path, input_size=128):
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 3
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            model_path, 
            sess_options, 
            providers=['CPUExecutionProvider']
        )
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    def preprocess(self, img_bgr):
        img_resized = cv2.resize(img_bgr, (self.input_size, self.input_size))
        # save_img_bgr(img_resized)
        gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
        enhanced = self.clahe.apply(gray)
        img_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
        # save_img_bgr(img_rgb)
        img_float = img_rgb.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.485, 0.485], dtype=np.float32)
        std = np.array([0.229, 0.229, 0.229], dtype=np.float32)
        img_normalized = (img_float - mean) / std
        img_chw = img_normalized.transpose(2, 0, 1)
        return np.expand_dims(img_chw, axis=0)

    def predict(self, eye_img, thres=0.7):
        if eye_img is None or eye_img.size == 0:
            return 0, 0.0
        input_tensor = self.preprocess(eye_img)
        outputs = self.session.run(
            None,
            {self.input_name: input_tensor}
        )
        logit = float(outputs[0][0][0])
        prob_open = 1.0 / (1.0 + np.exp(-logit))
        is_open = int(prob_open > thres)

        return is_open, prob_open

