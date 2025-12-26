import os
import glob
from datetime import datetime, timedelta
from nicegui import ui

async def create_history_page():
    ui.add_head_html('''             
        <style>
            body { background-color: #0f172a; color: #f8fafc; font-family: 'Roboto', sans-serif; }
            .history-card { 
                background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; overflow: hidden;
            }
            .bar-col {
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                border-radius: 4px;
                cursor: pointer;
            }
            .bar-selected {
                background-color: #3b82f6 !important;
                box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
                border: 1px solid rgba(255,255,255,0.8);
                transform: scaleY(1.05);
                z-index: 10;
            }
            .bar-data { background-color: #f97316; opacity: 0.85; }
            .bar-empty { background-color: #334155; opacity: 0.3; }
            video { width: 100%; height: 100%; border-radius: 8px; outline: none; background: #000; }
        </style>
    ''')

    img_dir = 'logs/log_frame'
    vid_dir = 'logs/videos' 
    
    if not os.path.exists(img_dir): os.makedirs(img_dir)
    if not os.path.exists(vid_dir): os.makedirs(vid_dir)

    date_options = {} 
    now = datetime.now()
    ordered_date_keys = []
    
    for i in range(7):
        d = now - timedelta(days=i)
        raw_str = d.strftime("%Y%m%d")
        label_str = d.strftime("Ngày %d/%m/%Y")
        if i == 0: label_str += " (Hôm nay)"
        elif i == 1: label_str += " (Hôm qua)"
        date_options[raw_str] = label_str
        ordered_date_keys.append(raw_str)

    grouped_data = { key: {slot: [] for slot in range(12)} for key in ordered_date_keys }
    valid_keys = set(grouped_data.keys())

    video_files_map = {} 
    all_vids = []
    all_vids.extend(glob.glob(os.path.join(vid_dir, "*.mp4")))
    all_vids.extend(glob.glob(os.path.join(vid_dir, "*.avi")))
    all_vids.extend(glob.glob(os.path.join(vid_dir, "*.mkv")))
    
    for v_path in sorted(all_vids):
        try:
            fname = os.path.basename(v_path)
            name_no_ext = os.path.splitext(fname)[0]
            parts = name_no_ext.split('_') 
            if len(parts) >= 3:
                d_str = parts[1]
                t_str = parts[2]
                dt_vid = datetime.strptime(f"{d_str}_{t_str}", "%Y%m%d_%H%M%S")
                
                if d_str not in video_files_map: video_files_map[d_str] = []
                video_files_map[d_str].append({
                    'dt': dt_vid,
                    'url': f'/captured_videos/{fname}',
                    'used': False,   
                })
        except: continue

    def find_matching_video(img_dt):
        d_key = img_dt.strftime("%Y%m%d")
        if d_key not in video_files_map: return None
        candidates = video_files_map[d_key]
        best_vid = None
        min_diff = 20.0 
        for vid in candidates:
            if vid['used']: continue
            diff = (vid['dt'] - img_dt).total_seconds()
            if diff < 0: continue
            if diff <= min_diff:
                min_diff = diff
                best_vid = vid
        if best_vid:
            best_vid['used'] = True 
            return best_vid['url']
        return None

    img_files = sorted(glob.glob(os.path.join(img_dir, "*.jpg")), reverse=True)
    
    for f_path in img_files:
        filename = os.path.basename(f_path)
        try:
            parts = filename.split('_')
            if len(parts) < 4: continue
            date_part = parts[2]
            time_part = parts[3].split('.')[0]
            
            if date_part in valid_keys:
                dt = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
                slot_idx = dt.hour // 2 
                vid_url = find_matching_video(dt)
                grouped_data[date_part][slot_idx].append({
                    'image_url': f'/captured_images/{filename}',
                    'video_url': vid_url, 
                    'display_time': dt.strftime("%H:%M:%S"),
                    'display_date': dt.strftime("%d/%m/%Y"),
                })
        except: continue

    
    LAYOUT_WIDTH = 'w-full max-w-[95%] 2xl:max-w-[1600px]'

    with ui.dialog().classes('w-full h-full backdrop-blur-md') as dialog:
        with ui.card().classes('w-full max-w-6xl bg-black p-0 items-center justify-center relative shadow-2xl border border-gray-800'):
            ui.button(icon='close', on_click=dialog.close).props('flat round color=white size=md').classes('absolute top-2 right-2 z-50 bg-black/50 hover:bg-black/70')
            media_container = ui.element('div').classes('w-full aspect-video flex items-center justify-center bg-black')

    def open_playback(item, mode='image'):
        media_container.clear()
        with media_container:
            if mode == 'video' and item.get('video_url'): 
                ui.html(f'''
                    <video autoplay controls playsinline style="width:100%; height:100%; object-fit:contain;">
                        <source src="{item['video_url']}" type="video/mp4">
                        <source src="{item['video_url']}" type="video/avi">
                        Trình duyệt không hỗ trợ định dạng video này.
                    </video>
                ''', sanitize=False)
            else:
                ui.image(item['image_url']).classes('max-w-full max-h-full object-contain')
        dialog.open()

    with ui.column().classes('w-full items-center p-4 pb-20 gap-6'):
        
        with ui.row().classes(f'{LAYOUT_WIDTH} justify-between items-center bg-slate-800 p-3 rounded-lg border border-slate-700'):
            with ui.row().classes('items-center gap-3'):
                ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')).props('flat round color=white size=sm')
                with ui.column().classes('gap-0'):
                    ui.label('NHẬT KÝ GIÁM SÁT').classes('text-[11px] font-bold text-slate-400 tracking-widest')
                    date_select = ui.select(options=date_options, value=ordered_date_keys[0]).props('dense borderless options-dense behavior=menu').classes('text-lg font-bold text-blue-400 min-w-[220px]')
            total_badge = ui.chip('0 Sự kiện').props('icon=history color=slate-700 text-color=white square')

        with ui.row().classes(f'{LAYOUT_WIDTH} justify-between px-1'):
            ui.label('Phân bố cảnh báo theo khung giờ (2 tiếng/cột)').classes('text-xs text-slate-500 italic')
            
        chart_container = ui.element('div').classes(f'{LAYOUT_WIDTH} h-60 bg-slate-900 rounded-xl p-4 flex items-end gap-2 border border-slate-800 relative mt-0')

        gallery_title = ui.label('').classes(f'text-lg font-bold text-slate-200 {LAYOUT_WIDTH} mt-6 border-b border-slate-700 pb-2')

        gallery_grid = ui.element('div').classes(f'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 {LAYOUT_WIDTH} mt-2')

        def render_gallery(slot_idx, items):
            gallery_grid.clear()
            start_h = slot_idx * 2
            time_str = f"{start_h:02d}:00 - {start_h+2:02d}:00"
            
            if not items:
                gallery_title.set_text(f'Khung giờ {time_str}')
                with gallery_grid:
                    ui.label('Không có dữ liệu vi phạm.').classes('col-span-full text-center text-slate-600 py-8 italic')
                return

            gallery_title.set_text(f'Chi tiết {time_str} ({len(items)} cảnh báo)')
            
            with gallery_grid:
                for item in items:
                    with ui.card().classes('history-card p-0 group hover:border-blue-500 transition-colors shadow-lg'):
                        
                        ui.image(item['image_url']).on('click', lambda e, i=item: open_playback(i, mode='image')) \
                            .classes('w-full aspect-video object-cover bg-black opacity-90 group-hover:opacity-100 cursor-pointer')
                        
                        with ui.row().classes('w-full px-3 py-2 bg-[#111827] justify-between items-center border-t border-slate-700 no-wrap'):
                            
                            with ui.column().classes('gap-0'):
                                ui.label(item['display_time']).classes('text-sm sm:text-base font-bold text-blue-400 font-mono leading-none mb-1')
                                ui.label(item['display_date']).classes('text-[10px] sm:text-[11px] font-medium text-slate-500 tracking-wide')
                            
                            if item['video_url']:
                                ui.button(icon='play_circle', on_click=lambda e, i=item: open_playback(i, mode='video')) \
                                    .props('flat round color=green size=sm') \
                                    .classes('animate-pulse hover:scale-110 transition-transform bg-green-900/20 shrink-0')
                            else:
                                ui.icon('photo', color='grey').classes('text-xl opacity-50 shrink-0')

        def render_chart(date_key, selected_slot=None):
            chart_container.clear()
            day_data = grouped_data[date_key]
            counts = [len(day_data[s]) for s in range(12)]
            max_val = max(counts) if max(counts) > 0 else 1
            total_badge.set_text(f'{sum(counts)} Cảnh báo')

            with chart_container:
                for s in range(12):
                    count = counts[s]
                    h_pct = max((count / max_val) * 100, 8)
                    is_active = (s == selected_slot)
                    bg_cls = 'bar-data' if count > 0 else 'bar-empty'
                    act_cls = 'bar-selected' if is_active else ''
                    
                    with ui.column().classes('flex-1 h-full justify-end items-center gap-1 group relative cursor-pointer') as col:
                        if count > 0 or is_active:
                            lbl_clr = 'text-blue-300' if is_active else 'text-white'
                            ui.label(str(count) if count > 0 else '0').classes(f"text-[10px] font-bold {lbl_clr} mb-[-2px]")
                        
                        ui.element('div').classes(f'w-full rounded-t-sm {bg_cls} {act_cls} bar-col').style(f'height: {h_pct}%;')
                        dh = s * 2
                        if dh % 4 == 0: ui.label(f'{dh}h').classes('text-[10px] text-slate-500 font-bold')
                        else: ui.element('div').classes('h-[14px]')
                        col.on('click', lambda e, idx=s: (render_chart(date_key, idx), render_gallery(idx, day_data[idx])))

        def on_date_change(e):
            slot = datetime.now().hour // 2 if e.value == ordered_date_keys[0] else 6
            render_chart(e.value, slot)
            render_gallery(slot, grouped_data[e.value][slot])

        date_select.on_value_change(on_date_change)
        
        curr_slot = datetime.now().hour // 2
        render_chart(ordered_date_keys[0], curr_slot)
        render_gallery(curr_slot, grouped_data[ordered_date_keys[0]][curr_slot])