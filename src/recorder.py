import cv2
import threading
import time
import os
import subprocess 
from collections import deque
from datetime import datetime

class EvidenceRecorder:
    def __init__(self, save_dir="logs/videos", buffer_seconds=5, fps=15):
        self.save_dir = save_dir
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        self.fps = fps
        self.buffer_size = buffer_seconds * fps
        self.frame_buffer = deque(maxlen=self.buffer_size)
        self.lock = threading.Lock()
        self.is_recording = False
        self.last_save_time = 0
        self.cooldown = 10 

    def update(self, frame):
        if frame is None: return
        with self.lock:
            self.frame_buffer.append(frame.copy())

    def save_evidence(self):
        now = time.time()
        if self.is_recording or (now - self.last_save_time < self.cooldown):
            return

        self.is_recording = True
        self.last_save_time = now
        threading.Thread(target=self._worker_save, daemon=True).start()

    def _worker_save(self):
        try:
            with self.lock:
                frames_to_save = list(self.frame_buffer)
            
            if not frames_to_save:
                self.is_recording = False
                return
            
            temp_filename = datetime.now().strftime("temp_%Y%m%d_%H%M%S.avi")
            temp_filepath = os.path.join(self.save_dir, temp_filename)
            
            final_filename = datetime.now().strftime("evidence_%Y%m%d_%H%M%S.mp4")
            final_filepath = os.path.join(self.save_dir, final_filename)

            h, w = frames_to_save[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'MJPG') # Codec này Pi xử lý rất nhẹ
            out = cv2.VideoWriter(temp_filepath, fourcc, self.fps, (w, h))

            for frame in frames_to_save:
                out.write(frame)
            out.release()
            
            print(f"[RECORDER] Converting to MP4: {final_filename}...")
            
            command = [
                'ffmpeg', '-y', 
                '-i', temp_filepath, 
                '-c:v', 'libx264',
                '-preset', 'ultrafast', 
                '-crf', '28', 
                '-pix_fmt', 'yuv420p', 
                final_filepath 
            ]
            
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
                
            print(f"[RECORDER] Saved web-ready video: {final_filepath}")

        except Exception as e:
            print(f"[RECORDER] Error: {e}")
        finally:
            self.is_recording = False