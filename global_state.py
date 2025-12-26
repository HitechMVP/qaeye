import threading
from src.config import ConfigManager

# Global locks and events
frame_lock = threading.Lock()
new_frame_event = threading.Event()
stop_event = threading.Event()

# Shared data
latest_jpeg_frame = None
global_cam_ref = None
global_gpio_enabled = False
global_led_pin = 21

# Constants
CAM_WIDTH = 1280
CAM_HEIGHT = 720
MIN_CROP_SIZE = 256

config_mgr = ConfigManager()