import cv2
import numpy as np
import subprocess
import re
import socket
import os
import glob
import requests
import asyncio
import logging
import yaml
from yaml import Loader
from pathlib import Path

import global_state as state

logger = logging.getLogger("utils")

async def perform_safe_reboot():
    logger.warning("Initiating SAFE REBOOT sequence...")
    state.stop_event.set()
    await asyncio.sleep(1.0)
    try:
        cleanup_resources(
            cam=state.global_cam_ref, 
            led_pin=state.global_led_pin, 
            gpio_enabled=state.global_gpio_enabled, 
            logger=logger
        )
        logger.info("Resources released successfully.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    await asyncio.sleep(1.0)
    os.system("(sleep 1 && systemctl reboot) &")

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
    
def get_current_wifi():
    try:
        try:
            ssid = subprocess.check_output("iwgetid -r", shell=True).decode().strip()
            if ssid:
                sig = subprocess.check_output("grep wlan0 /proc/net/wireless | awk '{print int($4)}'", shell=True).decode().strip()
                return ssid, f"{sig} dBm"
        except:
            pass
            
        result = subprocess.check_output("iw dev wlan0 link", shell=True, stderr=subprocess.STDOUT).decode()
        if "Not connected." in result:
            return None, "Not Connected"

        ssid_match = re.search(r'SSID:\s*(.+)', result)
        ssid = ssid_match.group(1).strip() if ssid_match else None

        signal_match = re.search(r'signal:\s*(-?\d+)\s*dBm', result)
        signal = f"{signal_match.group(1)} dBm" if signal_match else "Unknown"

        return ssid, signal
    except Exception:
        return None, "Not Connected"
    
def check_wifi_available(ssid):
    try:
        cmd = "nmcli -f SSID dev wifi list" 
        result = subprocess.check_output(cmd, shell=True, timeout=5, stderr=subprocess.DEVNULL).decode('utf-8')
        if re.search(r'\b' + re.escape(ssid) + r'\b', result, re.IGNORECASE):
            return True
        return False
    except subprocess.TimeoutExpired:
        print("Wifi scan timed out.")
        return False
    except Exception as e:
        print(f"Wifi scan error: {e}")
        return False 

def delete_all_wifi_profiles():
    try:
        cmd_list = "nmcli -t -f UUID,TYPE connection show"
        connections = subprocess.check_output(cmd_list, shell=True).decode().strip().split('\n')
        
        for conn in connections:
            if not conn: continue
            parts = conn.split(':')
            if len(parts) >= 2:
                uuid = parts[0]
                ctype = parts[1]
                if ctype == '802-11-wireless':
                    subprocess.call(f"nmcli connection delete uuid '{uuid}'", shell=True, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Error deleting profiles: {e}")
        return False
    
def configure_wifi_profile(ssid, psk):
    try:
        delete_all_wifi_profiles()
        add_cmd = f"nmcli con add type wifi ifname wlan0 con-name '{ssid}' ssid '{ssid}'"
        subprocess.check_call(add_cmd, shell=True)
        sec_cmd = f"nmcli con modify '{ssid}' wifi-sec.key-mgmt wpa-psk wifi-sec.psk '{psk}'"
        subprocess.check_call(sec_cmd, shell=True)
        prio_cmd = f"nmcli con modify '{ssid}' connection.autoconnect yes connection.autoconnect-priority 100"
        subprocess.check_call(prio_cmd, shell=True)
        retry_cmd = f"nmcli con modify '{ssid}' connection.autoconnect-retries 1"
        subprocess.check_call(retry_cmd, shell=True)
        return 0 
    except subprocess.CalledProcessError as e:
        return 1
    except Exception as e:
        return 2

def draw_hud_bbox(frame, pt1, pt2, pred=None, label_text="Open",
                  line_len=10, thickness=2, color_override=None, prob=None):

    if color_override is not None:
        color = color_override
    else:
        color = (0, 255, 0) if pred == 1 else (0, 0, 255)

    x1, y1 = pt1
    x2, y2 = pt2

    cv2.line(frame, (x1, y1), (x1 + line_len, y1), color, thickness)
    cv2.line(frame, (x1, y1), (x1, y1 + line_len), color, thickness)
    cv2.line(frame, (x2, y1), (x2 - line_len, y1), color, thickness)
    cv2.line(frame, (x2, y1), (x2, y1 + line_len), color, thickness)
    cv2.line(frame, (x1, y2), (x1 + line_len, y2), color, thickness)
    cv2.line(frame, (x1, y2), (x1, y2 - line_len), color, thickness)
    cv2.line(frame, (x2, y2), (x2 - line_len, y2), color, thickness)
    cv2.line(frame, (x2, y2), (x2, y2 - line_len), color, thickness)

    if label_text:
        font = cv2.FONT_HERSHEY_SIMPLEX
        if prob is not None:
            label = f"{label_text} {prob:.2f}"
        else:
            label = label_text

        cv2.putText(frame, label, (x1, y1 - 10), font, 0.5, color, 1, cv2.LINE_AA)

    return frame

def softmax(x):
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=-1, keepdims=True)

def get_log_data(limit=60):
    log_dir = "logs/log_frame"
    if not os.path.exists(log_dir):
        return []
    files = sorted(glob.glob(os.path.join(log_dir, "*.jpg")), key=os.path.getmtime, reverse=True)[:limit]
    results = []
    for file_path in files:
        filename = os.path.basename(file_path)
        try:
            parts = filename.split('_')
            if len(parts) < 4: continue
            date_part, time_part = parts[2], parts[3].split('.')[0]
            display_time = f"{date_part[6:]}/{date_part[4:6]}/{date_part[:4]} - {time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
            results.append({"display_time": display_time, "image_url": f"/captured_images/{filename}"})
        except Exception: continue
    return results

try:
    import RPi.GPIO as GPIO
    RPI_AVAILABLE = True
except RuntimeError:
    GPIO = None
    RPI_AVAILABLE = False

def initialize_gpio(led_pin, logger):
    """Initialize GPIO with error handling"""
    if not RPI_AVAILABLE:
        logger.warning("RPI.GPIO not available. GPIO features disabled.")
        return False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT)
        GPIO.output(led_pin, GPIO.LOW)
        logger.info(f"GPIO initialized on pin {led_pin}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize GPIO: {e}")
        return False

def set_relay(gpio_enabled, led_pin, logger, state):
    if not gpio_enabled: return
    try:
        GPIO.output(led_pin, GPIO.HIGH if state else GPIO.LOW)
    except Exception as e:
        logger.error(f"GPIO blink error: {e}")
  
def cleanup_resources(cam, led_pin, gpio_enabled, logger):
    """Cleanup all resources safely"""
    logger.info("Cleaning up resources...")
    try:
        if cam and cam.isOpened(): cam.release()
    except Exception as e: logger.error(f"Error closing camera: {e}")
    
    try: cv2.destroyAllWindows()
    except: pass
    
    if gpio_enabled and RPI_AVAILABLE:
        try:
            GPIO.output(led_pin, GPIO.LOW)
            GPIO.cleanup()
            logger.info("GPIO cleaned up")
        except: pass

def load_config(config_path='configs/configs.yaml'):
    try:
        if not Path(config_path).exists():
            return {}
        with open(config_path) as stream:
            return yaml.load(stream, Loader=Loader)
    except Exception as e:
        return {}

def perform_sync(server_ip, logger):
    if not server_ip:
        logger.error("Sync Error: Server IP is empty!")
        return "IP Address is missing!"

    server_ip = server_ip.strip() 
    
    if not server_ip.startswith("http"):
        base_url = f"http://{server_ip}"
    else:
        base_url = server_ip
        
    if ":" not in base_url.split("//")[-1]:
        base_url += ":8000"

    upload_url = f"{base_url}/upload"
    logger.info(f"Starting sync to: {upload_url}")

    folders_to_sync = [
        ("data/raw_yolo", "raw_yolo"),
        ("data/raw_eyes/open", "raw_eyes/open"),
        ("data/raw_eyes/closed", "raw_eyes/closed")
    ]

    total_files = 0
    success_count = 0
    fail_count = 0

    try:
        try: requests.get(base_url, timeout=3)
        except: pass

        for local_dir, remote_subfolder in folders_to_sync:
            if not os.path.exists(local_dir): continue
            
            files = glob.glob(os.path.join(local_dir, "*.jpg"))
            total_files += len(files)

            for file_path in files:
                filename = os.path.basename(file_path)
                try:
                    with open(file_path, 'rb') as f:
                        files_payload = {'file': (filename, f, 'image/jpeg')}
                        data_payload = {'sub_folder': remote_subfolder}
                        
                        response = requests.post(upload_url, files=files_payload, data=data_payload, timeout=5)
                        
                        if response.status_code == 200 and response.json().get("status") == "success":
                            f.close()
                            os.remove(file_path)
                            success_count += 1
                            print(f"Synced & Deleted: {filename}")
                        else:
                            fail_count += 1
                            logger.warning(f"Failed to upload {filename}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"Error syncing {filename}: {str(e)}")
                    
        result_msg = f"Sync Complete: Sent {success_count}/{total_files} files."
        if fail_count > 0:
            result_msg += f" ({fail_count} failed)"
        
        logger.info(result_msg)
        return result_msg

    except Exception as e:
        logger.error(f"Sync System Error: {str(e)}")
        return f"System Error: {str(e)}"