import numpy as np
import time

class EyeTracker:
    def __init__(self, drowsy_threshold=2.0):
        self.eye_timers = {} 
        self.drowsy_threshold = drowsy_threshold

    def filter_worker_eyes(self, all_boxes, frame_shape, mode=0):
        frame_h, frame_w = frame_shape[:2]
        frame_center = (frame_w // 2, frame_h // 2)
        
        eyes_with_center = []
        for box in all_boxes:
            x1, y1, x2, y2 = box
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            eyes_with_center.append((box, center))

        center_eyes = []
        out_of_center = []

        if not eyes_with_center:
            return [], []

        eyes_sorted = sorted(
            eyes_with_center,
            key=lambda b: (b[1][0]-frame_center[0])**2 + (b[1][1]-frame_center[1])**2
        )
        
        primary_eye = eyes_sorted[0]
        remaining_eyes = eyes_sorted[1:]

        if mode == 1:
            return [primary_eye[0]], [e[0] for e in remaining_eyes]


        if not remaining_eyes:
            return [primary_eye[0]], []

        best_partner = None
        p_box, p_center = primary_eye
        
        for cand in remaining_eyes:
            c_box, c_center = cand
            y_diff = abs(p_center[1] - c_center[1])
            max_y_diff = (p_box[3] - p_box[1]) * 1.5 
            
            if y_diff < max_y_diff:
                best_partner = cand
                break 
        
        if best_partner:
            if p_center[0] < best_partner[1][0]:
                center_eyes = [p_box, best_partner[0]]
            else:
                center_eyes = [best_partner[0], p_box]
            out_of_center = [e[0] for e in remaining_eyes if not np.array_equal(e[0], best_partner[0])]
        else:
            center_eyes = [p_box]
            out_of_center = [e[0] for e in remaining_eyes]

        return center_eyes, out_of_center

    def update_drowsiness(self, eye_index, state_label):
        key = eye_index 
        current_time = time.time()
        is_drowsy = False

        if state_label == 0:  
            if self.eye_timers.get(key) is None:
                self.eye_timers[key] = current_time
            elif current_time - self.eye_timers[key] >= self.drowsy_threshold:
                is_drowsy = True
        else:  
            self.eye_timers[key] = None
            
        return is_drowsy

    def reset(self):
        self.eye_timers = {}