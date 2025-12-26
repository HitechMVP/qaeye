import os
import time
import datetime


DIRS_TO_CLEAN = [
    "./logs/log_frame",
    "./logs/videos"
]

DAYS_TO_KEEP = 7
SECONDS_TO_KEEP = DAYS_TO_KEEP * 86400

def cleanup_files():
    now = time.time()
    print(f"[{datetime.datetime.now()}] Bắt đầu dọn dẹp logs cũ hơn {DAYS_TO_KEEP} ngày...")
    
    deleted_count = 0
    
    for folder in DIRS_TO_CLEAN:
        if not os.path.exists(folder):
            print(f"Thư mục không tồn tại: {folder}, bỏ qua.")
            continue

        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            
            if os.path.isfile(file_path):
                file_age = os.path.getmtime(file_path)
                
                if now - file_age > SECONDS_TO_KEEP:
                    try:
                        os.remove(file_path)
                        print(f"Đã xóa: {filename}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"Lỗi khi xóa {filename}: {e}")
                        
    print(f"[{datetime.datetime.now()}] Hoàn tất. Tổng số file đã xóa: {deleted_count}")

if __name__ == "__main__":
    cleanup_files()