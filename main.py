import threading
from nicegui import ui, app
from src.logger import create_log
from src.utils import cleanup_resources

import global_state as state
from src.detection import run_detection_thread
from src.streaming import get_video_feed_response
from src.pages.dashboard import create_main_page
from src.pages.history import create_history_page

logger = create_log()

@app.get("/video_feed")
def video_feed():
    return get_video_feed_response()

@ui.page('/')
async def main_page():
    await create_main_page(logger)

@ui.page('/history')
async def history_page():
    await create_history_page()

app.add_static_files('/captured_images', 'logs/log_frame')
app.add_static_files('/captured_videos', 'logs/videos')

t = threading.Thread(target=run_detection_thread, args=(logger,), daemon=True)
t.start()

async def shutdown_handler():
    state.stop_event.set()
    try:
        cleanup_resources(
            cam=state.global_cam_ref, 
            led_pin=state.global_led_pin, 
            gpio_enabled=state.global_gpio_enabled, 
            logger=logger
        )
    except: pass

app.on_shutdown(shutdown_handler)
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='Q-AEye Monitor', port=80, reload=False, dark=True)
    logger.info("Application Terminated")