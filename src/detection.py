import time
import cv2
from collections import deque
from datetime import datetime

from src.models import YOLOModel, EyeClassifier
from src.tracker import EyeTracker
from src.utils import draw_hud_bbox, initialize_gpio, set_relay
from src.recorder import EvidenceRecorder
from src.logger import save_suspected_frame
import global_state as state
import os 


def run_detection_thread(logger):

    # Initialize Recorder
    recorder = EvidenceRecorder(save_dir="logs/videos", buffer_seconds=3, fps=15)
    
    # Init Models & Hardware
    EYE_CROP_SIZE = state.config_mgr.get("eye_img_size")
    led_pin = state.config_mgr.get("led_pin", 21)
    
    gpio_enabled = initialize_gpio(led_pin, logger)
    state.global_led_pin = led_pin
    state.global_gpio_enabled = gpio_enabled
    
    yolo_path = state.config_mgr.get("yolo_path", "weights/new-best.onnx")
    eye_path = state.config_mgr.get("eye_model_path", "weights/eye_model.onnx")
    
    yolo = YOLOModel(
        yolo_path, 
        input_size=state.config_mgr.get("yolo_img_size", 224), 
        conf_thres=state.config_mgr.get("conf_threshold", 0.3), 
        iou_thres=state.config_mgr.get("iou_threshold", 0.35)
    )
    classifier = EyeClassifier(eye_path, input_size=EYE_CROP_SIZE)
    tracker = EyeTracker(drowsy_threshold=state.config_mgr.get("drowsy_time_threshold", 2.0))

    prob_history = {"left": deque(maxlen=5), "right": deque(maxlen=5)}

    # Init Camera
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, state.CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, state.CAM_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
    state.global_cam_ref = cap 

    # Loop variables
    FRAME_SKIP = 2
    frame_count = 0
    last_worker_eyes = []
    last_other_eyes = []
    relay_on = False
    is_drowsy_alert = False
    MAX_MISSING_FRAMES = 15
    missing_frame_counter = 0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 45]


    YOLO_DATA_DIR = "data/raw_yolo"
    EYE_OPEN_DIR = "data/raw_eyes/open"
    EYE_CLOSED_DIR = "data/raw_eyes/closed"
    if not os.path.exists(YOLO_DATA_DIR): os.makedirs(YOLO_DATA_DIR)
    if not os.path.exists(EYE_OPEN_DIR): os.makedirs(EYE_OPEN_DIR)
    if not os.path.exists(EYE_CLOSED_DIR): os.makedirs(EYE_CLOSED_DIR)
    last_data_save_time = 0
    
    while not state.stop_event.is_set():

        current_conf = state.config_mgr.get("conf_threshold", 0.3)
        current_drowsy_time = state.config_mgr.get("drowsy_time_threshold", 2.0)
        logic_mode = int(state.config_mgr.get("eye_logic_mode", 0)) 
        
        if yolo.conf_thres != current_conf: yolo.conf_thres = current_conf
        if tracker.drowsy_threshold != current_drowsy_time: tracker.drowsy_threshold = current_drowsy_time

        ret, frame_orig = cap.read()

        recorder.update(frame_orig)

        if not ret or frame_orig is None or frame_orig.size == 0:
            time.sleep(0.5)
            continue

        should_save_data = False
        current_timestamp = int(time.time())
        is_collecting = state.config_mgr.get("data_collection_enabled", False)
        collection_interval = state.config_mgr.get("data_collection_interval", 10.0)
        if is_collecting:
            if time.time() - last_data_save_time >= collection_interval:
                should_save_data = True
                last_data_save_time = time.time()
        
        h_img, w_img = frame_orig.shape[:2]
        crop_enabled = bool(state.config_mgr.get("crop_enabled", False))
        
        # Crop Logic
        if crop_enabled:
            cx, cy = int(state.config_mgr.get("crop_x", 0)), int(state.config_mgr.get("crop_y", 0))
            cw, ch = int(state.config_mgr.get("crop_w", w_img)), int(state.config_mgr.get("crop_h", h_img))
            cx, cy = max(0, min(cx, w_img - 1)), max(0, min(cy, h_img - 1))
            cw, ch = max(state.MIN_CROP_SIZE, min(cw, w_img - cx)), max(state.MIN_CROP_SIZE, min(ch, h_img - cy))
            proc_frame = frame_orig[cy:cy+ch, cx:cx+cw]
            if proc_frame.size == 0 or proc_frame.shape[0] < state.MIN_CROP_SIZE or proc_frame.shape[1] < state.MIN_CROP_SIZE:
                 proc_frame, crop_enabled = frame_orig, False
        else:
            proc_frame = frame_orig
        
        if should_save_data:
            try:
                yolo_fname = f"{YOLO_DATA_DIR}/{current_timestamp}.jpg"
                cv2.imwrite(yolo_fname, proc_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                logger.info(f"Saved YOLO Frame: {yolo_fname}")
            except Exception as e:
                logger.error(f"Save YOLO failed: {e}")

        # Detection Logic (Skip Frames)
        if frame_count % FRAME_SKIP == 0:
            frame_count = 0
            all_boxes = yolo.detect(proc_frame)
            if crop_enabled and all_boxes:
                for b in all_boxes:
                    b[0] += cx; b[1] += cy; b[2] += cx; b[3] += cy
            worker_eyes, other_eyes = tracker.filter_worker_eyes(all_boxes, frame_orig.shape, mode=logic_mode)
            last_worker_eyes, last_other_eyes = worker_eyes, other_eyes
        else:
            worker_eyes, other_eyes = last_worker_eyes, last_other_eyes
            
        display_frame = frame_orig
        frame_count += 1
        
        # Missing Frame Handling
        if len(worker_eyes) == 0:
            prob_history["left"].clear()
            prob_history["right"].clear()
            missing_frame_counter += 1
            if missing_frame_counter > MAX_MISSING_FRAMES:
                tracker.reset()
                is_drowsy_alert = False
                missing_frame_counter = 0
        else:
            missing_frame_counter = 0
        
        # Eye Classification & Update Status
        eye_statuses = []
        eye_closed_thres = state.config_mgr.get("eye_closed_threshold", 0.8)
        
        for i, box in enumerate(worker_eyes):
            try:
                x1, y1, x2, y2 = map(int, box)
                y2 = y2 + int((y2 - y1) / 4)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(display_frame.shape[1], x2), min(display_frame.shape[0], y2)
                if x1 >= x2 or y1 >= y2: continue
                eye_crop = display_frame[y1:y2, x1:x2]
                if eye_crop.size == 0: continue


                _, prob_raw = classifier.predict(eye_crop, thres=eye_closed_thres)
                
                key = "left" if i == 0 else "right"
                prob_history[key].append(prob_raw)
                avg_prob = sum(prob_history[key]) / len(prob_history[key])
                final_pred = 1 if avg_prob > eye_closed_thres else 0

                if should_save_data:
                    try:
                        eye_side = "left" if i == 0 else "right"
                        
                        if final_pred == 1:
                            target_dir = EYE_OPEN_DIR
                            label_str = "open"
                        else:
                            target_dir = EYE_CLOSED_DIR
                            label_str = "closed"

                        eye_fname = f"{target_dir}/{current_timestamp}_{eye_side}_{label_str}.jpg"
                        cv2.imwrite(eye_fname, eye_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                    except Exception as e:
                        logger.error(f"Save Eye failed: {e}")
                
                is_this_eye_drowsy = tracker.update_drowsiness(i, final_pred)
                eye_statuses.append(is_this_eye_drowsy)
                
                label = "Open" if final_pred == 1 else "Closed"
                display_frame = draw_hud_bbox(display_frame, (x1, y1), (x2, y2), pred=final_pred, label_text=label, prob=avg_prob)
            except: continue

        # Alert Logic
        should_alert = False
        if all(eye_statuses):
            if (logic_mode == 0 and len(eye_statuses) == 2) or (logic_mode == 1 and len(eye_statuses) == 1):
                should_alert = True

        if should_alert:
            if not is_drowsy_alert:
                try: 
                    save_suspected_frame(display_frame)
                    recorder.save_evidence()
                except: pass
            is_drowsy_alert = True
            cv2.putText(display_frame, "DROWSY!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
        else:
            is_drowsy_alert = False
            
        for box in other_eyes:
            x1, y1, x2, y2 = map(int, box)
            display_frame = draw_hud_bbox(display_frame, (x1, y1), (x2, y2), pred=None, label_text="Ignored", color_override=(192,192,192))

        # Relay Control
        if is_drowsy_alert and not relay_on:
            set_relay(gpio_enabled, led_pin, logger, True)
            relay_on = True
        elif not is_drowsy_alert and relay_on:
            set_relay(gpio_enabled, led_pin, logger, False)
            relay_on = False

        if crop_enabled: cv2.rectangle(display_frame, (cx, cy), (cx+cw, cy+ch), (0, 255, 255), 2)

        # Draw Timestamp
        dt_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        height = display_frame.shape[0]
        position = (10, height - 20) 
        cv2.putText(display_frame, dt_string, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(display_frame, dt_string, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)

        # Update Global Frame
        ret, buffer = cv2.imencode('.jpg', display_frame, encode_params)
        if ret:
            with state.frame_lock:
                state.latest_jpeg_frame = buffer.tobytes()
                state.new_frame_event.set()

    # Cleanup when loop ends
    cap.release()
    set_relay(gpio_enabled, led_pin, logger, False)