import time
import asyncio
from nicegui import ui, run
from src.utils import get_current_wifi, get_ip_address, check_wifi_available, configure_wifi_profile, delete_all_wifi_profiles, perform_safe_reboot, perform_sync
import global_state as state

def create_main_page(logger):
    ui.add_head_html('''
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body { margin: 0; background: #000; overflow: hidden; }
            .video-container { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; }
            .ui-overlay { position: relative; z-index: 1000; }
            .control-btn { background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.3); }
            
            /* Custom Scrollbar for Drawer */
            ::-webkit-scrollbar { width: 6px; }
            ::-webkit-scrollbar-track { background: #1e1e1e; }
            ::-webkit-scrollbar-thumb { background: #555; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #888; }
            
            .setting-card { background-color: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 12px; }
        </style>
    ''')

    ts = int(time.time())
    ui.add_body_html(f'''
        <div class="video-container">
            <img id="cam-stream" src="/video_feed?t={ts}" style="width:100%; height:100%; object-fit:contain;"
                 onerror="setTimeout(()=>this.src='/video_feed?t='+Date.now(), 1000)">
        </div>
    ''')

    with ui.right_drawer(value=False).classes('bg-[#111827] text-white q-pa-md ui-overlay').props('width=340 behavior="mobile" overlay') as drawer:
        # HEADER
        with ui.row().classes('w-full items-center justify-between mb-4'):
             ui.label('⚙️ SYSTEM CONFIG').classes('text-xl font-bold tracking-wider text-slate-200')
             ui.button(icon='close', on_click=drawer.toggle).props('flat round dense color=grey-6')


        with ui.card().classes('setting-card w-full p-4 mb-4 border border-grey-8'):
            with ui.row().classes('justify-between w-full items-center mb-2'):
                ui.label('Wi-Fi Configuration').classes('text-lg font-semibold text-blue-300')
                refresh_btn = ui.button(icon='refresh').props('flat round dense color=grey-5')

            with ui.column().classes('w-full gap-1 mb-3'):
                with ui.row().classes('items-center gap-2 px-3 py-2 rounded border no-wrap w-full transition-colors duration-300') as pill_container:
                    status_mini_icon = ui.icon('help_outline', size='sm').classes('shrink-0 transition-colors duration-300')
                    with ui.column().classes('gap-0'):
                        ssid_label = ui.label('Unknown').classes('text-sm font-bold leading-tight')
                        ip_label = ui.label('IP: ...').classes('text-xs text-grey-4 font-mono')

            async def update_wifi_ui():
                refresh_btn.props('loading')
                wifi_data = await run.io_bound(get_current_wifi)
                if wifi_data and isinstance(wifi_data, (tuple, list)) and len(wifi_data) == 2:
                    ssid, signal = wifi_data
                else:
                    ssid, signal = None, "Initializing..."
                ip = await run.io_bound(get_ip_address) 
                
                if ssid:
                    pill_container.classes('bg-green-500/10 border-green-500/30', remove='bg-red-500/10 border-red-500/30')
                    ssid_label.set_text(f"{ssid} ({signal})")
                    ssid_label.classes('text-green-300', remove='text-red-300')
                    ip_label.set_text(f"IP: {ip}")
                    status_mini_icon.props('name=wifi color=green-400')
                else:
                    pill_container.classes('bg-red-500/10 border-red-500/30', remove='bg-green-500/10 border-green-500/30')
                    ssid_label.set_text("Disconnected")
                    ssid_label.classes('text-red-300', remove='text-green-300')
                    ip_label.set_text("IP: No Network")
                    status_mini_icon.props('name=signal_wifi_off color=red-400')
                refresh_btn.props(remove='loading')

            refresh_btn.on_click(update_wifi_ui)
            
            with ui.expansion('Configure New Wi-Fi', value=False).props('dense'):
                ui.label('⚠️ Overwrites existing connection!').classes('text-xs text-orange-400 mb-2 italic')
                ssid_input = ui.input(label='Wi-Fi Name (SSID)', placeholder='Enter Wi-Fi name').props('outlined dense dark color=blue').classes('mb-2')
                psk_input = ui.input(label='Password', placeholder='Min 8 characters').props('outlined dense dark password').classes('mb-2')

                with ui.row().classes('items-center gap-2 mb-3'):
                    show_pass = ui.checkbox('Show Password')
                    def toggle_pass():
                        psk_input.props('type=text' if show_pass.value else 'type=password')
                    show_pass.on_value_change(toggle_pass)

                async def save_wifi_settings(btn):
                    try:
                        btn.props('loading')
                        ssid = ssid_input.value.strip()
                        psk = psk_input.value.strip()

                        if not ssid:
                            ui.notify("Error: Wi-Fi Name (SSID) cannot be empty!", type='negative')
                            return
                        if len(psk) < 8:
                            ui.notify("Error: Password must be at least 8 characters!", type='negative')
                            return

                        ui.notify(f"Checking if '{ssid}' is available...", type='info', spinner=True)
                        wifi_exists = await run.io_bound(check_wifi_available, ssid)

                        if not wifi_exists:
                            ui.notify(f"Error: Network '{ssid}' not found nearby!", type='negative')
                            return

                        ui.notify("Saving new config...", type='info', spinner=True)
                        exit_code = await run.io_bound(configure_wifi_profile, ssid, psk)

                        if exit_code != 0:
                            raise Exception("Failed to configure Wi-Fi.")

                        with ui.dialog().classes('backdrop-blur-sm') as dialog:
                            with ui.card().classes('bg-gray-900 text-white'):
                                with ui.column().classes('items-center p-4'):
                                    ui.icon('check_circle', size='4rem', color='green-500')
                                    ui.label('SAVED!').classes('text-xl font-bold text-green-500 mt-2')
                                    ui.label(f"System will reboot to connect to: {ssid}").classes('text-sm text-center text-grey-4')
                                    ui.label('Rebooting in 3 seconds...').classes('text-red-400 font-bold mt-3')
                                    ui.spinner('dots', size='lg', color='red')
                            dialog.open()
                        await asyncio.sleep(2)
                        await perform_safe_reboot()
                    except Exception as e:
                        ui.notify(f"System Error: {str(e)}", type='negative', timeout=10.0)
                    finally:
                        btn.props(remove='loading')

                btn_save = ui.button('SAVE & REBOOT', icon='save', on_click=lambda: save_wifi_settings(btn_save)).props('color=blue-600 w-full rounded unelevated size=md').classes('hover:bg-blue-700 font-bold')

            ui.separator().classes('bg-grey-8 my-3')
            ui.label('DANGER ZONE').classes('text-xs font-bold text-red-500 mb-1')

            async def handle_wifi_reset():
                with ui.dialog() as dialog:
                    with ui.card().classes('bg-gray-900 border border-red-600'):
                        with ui.column().classes('items-center p-2'):
                            ui.icon('warning', size='xl', color='red')
                            ui.label('CONFIRM RESET?').classes('text-lg font-bold text-red-500')
                            ui.label('This will DELETE ALL Wi-Fi profiles.').classes('text-white')
                            ui.label('System will reboot to Hotspot mode.').classes('text-grey-4 text-sm mb-4')
                            with ui.row():
                                ui.button('CANCEL', on_click=dialog.close).props('flat color=white')
                                async def do_reset():
                                    dialog.close()
                                    ui.notify('Deleting all Wi-Fi profiles...', type='warning', spinner=True)
                                    await run.io_bound(delete_all_wifi_profiles)
                                    ui.notify('Rebooting system...', type='negative')
                                    await asyncio.sleep(1)
                                    await perform_safe_reboot()
                                ui.button('RESET & REBOOT', on_click=do_reset).props('color=red unelevated icon=restart_alt')
                dialog.open()

            ui.button('RESET WI-FI & REBOOT', icon='delete_forever', on_click=handle_wifi_reset).props('color=red-700 w-full rounded unelevated size=md').classes('hover:bg-red-800 font-bold')


        with ui.column().classes('w-full gap-3'):
            ui.label('🤖 AI INTELLIGENCE').classes('text-xs font-bold text-slate-500 tracking-widest mt-2')

            with ui.card().classes('setting-card w-full shadow-lg'):
                # YOLO CONFIDENCE
                with ui.row().classes('w-full justify-between items-center mb-1'):
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('visibility', size='xs', color='blue-400')
                        ui.label('Detection Confidence').classes('text-sm font-medium text-slate-300')
                    ui.label('YOLO').classes('text-[10px] bg-blue-900 text-blue-300 px-1 rounded')

                ui.slider(
                    min=0.05, max=1.0, step=0.05,
                    value=state.config_mgr.get("conf_threshold", 0.3),
                    on_change=lambda e: state.config_mgr.set("conf_threshold", round(float(e.value), 2))
                ).props('label-always dense color=blue').classes('w-full mt-6 mb-4')  # <--- THÊM mt-6

                # EYE CLOSED THRESHOLD
                with ui.row().classes('w-full justify-between items-center mb-1'):
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('remove_red_eye', size='xs', color='purple-400')
                        ui.label('Eye Close Threshold').classes('text-sm font-medium text-slate-300')
                    ui.label('SENSITIVITY').classes('text-[10px] bg-purple-900 text-purple-300 px-1 rounded')

                ui.slider(
                    min=0.05, max=0.95, step=0.05,
                    value=state.config_mgr.get("eye_closed_threshold", 0.8),
                    on_change=lambda e: state.config_mgr.set("eye_closed_threshold", round(float(e.value), 2))
                ).props('label-always dense color=purple').classes('w-full mt-6')  # <--- THÊM mt-6


        with ui.column().classes('w-full gap-3'):
            ui.label('🚨 ALERT & LOGIC').classes('text-xs font-bold text-slate-500 tracking-widest mt-2')
            
            with ui.card().classes('setting-card w-full shadow-lg border-red-900/50'):
                # DROWSY TIME
                with ui.row().classes('w-full justify-between items-center mb-2'):
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('timer', size='xs', color='red-400')
                        ui.label('Max Closed Time (s)').classes('text-sm font-bold text-red-200')
                
                ui.slider(
                    min=0.5, max=5.0, step=0.5,
                    value=state.config_mgr.get("drowsy_time_threshold", 2.0),
                    on_change=lambda e: state.config_mgr.set("drowsy_time_threshold", round(float(e.value), 1))
                ).props('label-always dense color=red').classes('w-full mt-6 mb-4')  # <--- THÊM mt-6

                ui.separator().classes('bg-slate-700 my-2')

                with ui.row().classes('w-full justify-between items-center'):
                    with ui.column().classes('gap-0'):
                        ui.label('Single Eye Mode').classes('text-sm font-bold text-orange-300')
                        ui.label('For side profile / partial face').classes('text-[10px] text-slate-400')
                    
                    ui.switch(
                        '',
                        value=int(state.config_mgr.get("eye_logic_mode", 0)) == 1,
                        on_change=lambda e: (
                            state.config_mgr.set("eye_logic_mode", 1 if e.value else 0),
                            ui.notify(f"Mode: {'1 Eye' if e.value else '2 Eyes (Auto)'}")
                        )
                    ).props('dense color=orange')


        with ui.column().classes('w-full gap-3 mb-6'):
            with ui.row().classes('w-full justify-between items-end mt-2'):
                ui.label('📐 CAMERA CROP').classes('text-xs font-bold text-slate-500 tracking-widest')
                
                ui.switch(
                    'Active',
                    value=state.config_mgr.get("crop_enabled"),
                    on_change=lambda e: state.config_mgr.set("crop_enabled", e.value)
                ).props('dense color=green right-label').classes('text-xs text-green-400')

            with ui.card().classes('setting-card w-full shadow-lg border-teal-900/30'):
                ui.label('Horizontal (X / Width)').classes('text-[11px] font-bold text-teal-200/70 mb-1')
                with ui.row().classes('w-full gap-2 items-center mb-3 no-wrap'):
                    ui.icon('swap_horiz', size='xs', color='teal')
                    ui.slider(min=0, max=state.CAM_WIDTH, step=10, 
                            value=state.config_mgr.get("crop_x", 0),
                            on_change=lambda e: state.config_mgr.set("crop_x", int(e.value))) \
                        .props('label-always dense color=teal').classes('col-grow')
                    
                    ui.slider(min=state.MIN_CROP_SIZE, max=state.CAM_WIDTH, step=10, 
                            value=state.config_mgr.get("crop_w", state.CAM_WIDTH),
                            on_change=lambda e: state.config_mgr.set("crop_w", int(e.value))) \
                        .props('label-always dense color=cyan').classes('col-grow')

                ui.label('Vertical (Y / Height)').classes('text-[11px] font-bold text-blue-200/70 mb-1')
                with ui.row().classes('w-full gap-2 items-center no-wrap'):
                    ui.icon('swap_vert', size='xs', color='blue')
                    ui.slider(min=0, max=state.CAM_HEIGHT, step=10, 
                            value=state.config_mgr.get("crop_y", 0),
                            on_change=lambda e: state.config_mgr.set("crop_y", int(e.value))) \
                        .props('label-always dense color=blue').classes('col-grow')
                    
                    ui.slider(min=state.MIN_CROP_SIZE, max=state.CAM_HEIGHT, step=10, 
                            value=state.config_mgr.get("crop_h", state.CAM_HEIGHT),
                            on_change=lambda e: state.config_mgr.set("crop_h", int(e.value))) \
                        .props('label-always dense color=indigo').classes('col-grow')
                
        with ui.column().classes('w-full gap-3 mb-6'):
            ui.label('🛠️ DATASET COLLECTION').classes('text-xs font-bold text-slate-500 tracking-widest mt-2')
            
            with ui.card().classes('setting-card w-full shadow-lg border-yellow-900/50'):
                with ui.row().classes('w-full justify-between items-center mb-2'):
                    with ui.column().classes('gap-0'):
                        ui.label('Auto Capture Mode').classes('text-sm font-bold text-yellow-500')
                        ui.label('Save raw images for training').classes('text-[10px] text-slate-400')
                    
                    ui.switch(
                        '',
                        value=state.config_mgr.get("data_collection_enabled", False),
                        on_change=lambda e: state.config_mgr.set("data_collection_enabled", e.value)
                    ).props('dense color=yellow icon=cloud_upload')

                with ui.row().classes('w-full justify-between items-center mb-1'):
                    with ui.row().classes('items-center gap-1'):
                        ui.icon('timer', size='xs', color='yellow-600')
                        ui.label('Interval (s)').classes('text-sm font-medium text-slate-300')
                    ui.label().bind_text_from(state.config_mgr.config, 'data_collection_interval', backward=lambda x: f"{int(x or 10)}s").classes('text-xs font-bold text-yellow-500')

                ui.slider(
                    min=1, max=60, step=1,
                    value=state.config_mgr.get("data_collection_interval", 10),
                    on_change=lambda e: state.config_mgr.set("data_collection_interval", int(e.value))
                ).props('label-always dense color=yellow').classes('w-full mb-4')

                ui.separator().classes('bg-slate-700 mb-4')

                ui.label('CLOUD SYNC').classes('text-[10px] font-bold text-slate-500 mb-2')

                with ui.dialog().props('persistent') as loading_dialog:
                    with ui.card().classes('flex-row items-center gap-4 bg-gray-900 border border-yellow-600 p-6'):
                        ui.spinner('dots', size='lg', color='yellow')
                        with ui.column().classes('gap-0'):
                            ui.label('ĐANG ĐỒNG BỘ...').classes('text-yellow-500 font-bold text-lg')
                            ui.label('Vui lòng không tắt máy').classes('text-gray-400 text-xs')
                
                server_ip_input = ui.input(
                    label='Server IP Address',
                    placeholder='192.168.1.x:8000',
                    value=state.config_mgr.get("server_sync_ip", "")
                ).props('outlined dense dark color=yellow').classes('w-full mb-2')
                
                server_ip_input.on_value_change(lambda e: state.config_mgr.set("server_sync_ip", e.value))

                async def on_sync_click():
                    ip = server_ip_input.value.strip()
                    state.config_mgr.set("server_sync_ip", ip)
                    state.config_mgr.save()
                    
                    if not ip:
                        ui.notify('Vui lòng nhập IP Server!', type='negative')
                        return

                    loading_dialog.open() 
                    sync_btn.props('loading')
                    
                    try:

                        msg = await run.io_bound(perform_sync, ip, logger)
                    finally:
                        loading_dialog.close() 
                        sync_btn.props(remove='loading')
                    
                    if "Error" in msg:
                        ui.notify(msg, type='negative', timeout=5000)
                    else:
                        ui.notify(msg, type='positive')

                sync_btn = ui.button('SYNC DATA NOW', icon='cloud_upload', on_click=on_sync_click) \
                    .props('color=yellow-900 text-color=yellow-100 w-full') \
                    .classes('font-bold border border-yellow-700/50')

        ui.button('APPLY & SAVE SETTINGS', on_click=lambda: (state.config_mgr.save(), ui.notify('✅ Settings Saved!'))) \
            .props('color=blue-grey-9 w-full icon=save_as').classes('font-bold border border-slate-600 hover:bg-slate-700')
        
        

    with ui.row().classes('absolute-top-right q-ma-md ui-overlay gap-2'):
        ui.button('SETTINGS', icon='settings', on_click=drawer.toggle).classes('control-btn text-white')
        ui.button('HISTORY', icon='history', on_click=lambda: ui.navigate.to('/history')).classes('control-btn text-blue-300')
    
    # Initialize wifi status
    return update_wifi_ui()