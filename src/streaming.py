import cv2
import numpy as np
from fastapi.responses import StreamingResponse
import global_state as state

def gen_frames():
    empty_frame = np.zeros((state.CAM_HEIGHT, state.CAM_WIDTH, 3), dtype=np.uint8)
    _, encoded_empty = cv2.imencode('.jpg', empty_frame)
    backup_frame = encoded_empty.tobytes()

    while True:
        if state.new_frame_event.wait(timeout=1.0):
            with state.frame_lock:
                if state.latest_jpeg_frame:
                    data = state.latest_jpeg_frame
                    backup_frame = state.latest_jpeg_frame 
                else:
                    data = backup_frame
            state.new_frame_event.clear()
        else:
            data = backup_frame

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n')

def get_video_feed_response():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")