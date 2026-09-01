from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO
import json
import threading
import time
from datetime import datetime
import psutil
from config import (EEPROM_WINDOW_START, EEPROM_WINDOW_END, EEPROM_PAGE_SIZE)
from eeprom import EEPROM
from can_monitor import get_can_status
from mqtt_client import MQTTClient
from log_exporter import LogExporter
from sensor_reader import get_temp_hum
from charger_interface import ChargerInterface
from battery_interface import BatteryInterface
from backup_logic import poll_for_discharge
from indicator import PushbuttonMonitor

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ========== COMPONENTS ==========
eeprom = EEPROM()
mqtt_client = MQTTClient(socketio)
log_exporter = LogExporter(mqtt_client)
charger = ChargerInterface()
battery = BatteryInterface()
pushbutton = PushbuttonMonitor()

tester_info_submitted = False
testername = pcbserial = modelnumber = projectdetail = None

_status_thread_started = False
_backup_test_lock = threading.Lock()
_backup_test_running = False


# ========== EEPROM HELPERS ==========
def safe_clean(raw):
    if not raw:
        return b""
    arr = bytearray(raw)
    while arr and (arr[-1] == 0xFF or arr[-1] == 0x00):
        arr.pop()
    return bytes(arr)


def _clear_eeprom_range(start_addr, end_addr, block_size=EEPROM_PAGE_SIZE):
    length = end_addr - start_addr
    if length <= 0:
        return
    chunk = [0x00] * block_size
    addr = start_addr
    while addr < end_addr:
        remaining = end_addr - addr
        write_len = min(block_size, remaining)
        eeprom.write_eeprom(addr, chunk[:write_len])
        addr += write_len


# ========== BACKGROUND THREADS ==========
def status_bar_monitor():
    """Drives every status-bar pill: CPU, CAN, temp/hum, EEPROM, MQTT, and feeds log_exporter."""
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)

        temp_data = get_temp_hum()
        temp = temp_data.get("temperature")
        hum = temp_data.get("humidity")

        can_status = get_can_status()

        eeprom_present = eeprom.probe()

        mqtt_connected = mqtt_client.connected
        mqtt_reachable = mqtt_client.ping_broker()

        log_exporter.set_environment_data(temp, hum, cpu_usage)
        log_exporter.set_can_status(can_status)
        log_exporter.set_eeprom_status(eeprom_present)
        log_exporter.set_mqtt_status(mqtt_connected, mqtt_reachable)

        socketio.emit('status_bar_update', {
            "cpu": cpu_usage,
            "temperature": temp,
            "humidity": hum,
            "can": can_status,
            "eeprom": {"present": eeprom_present},
            "mqtt": {"connected": mqtt_connected, "reachable": mqtt_reachable},
        })
        time.sleep(4)


def charger_poll_loop():
    def on_update(data):
        working, message = ChargerInterface.is_working(data)
        log_exporter.set_charger_status(data, working, message)
        socketio.emit('charger_data', {"data": data, "working": working, "message": message})
    charger.poll_forever(interval=1.5, on_update=on_update)


def battery_poll_loop():
    def on_update(data):
        working, message = BatteryInterface.is_working(data)
        log_exporter.set_battery_status(data, working, message)
        # Report the session-latched verdict to the UI, not just the instantaneous one,
        # so the Battery tab doesn't flip to "error" the moment AC/charger is removed
        # for the backup test (see log_exporter.set_battery_status()).
        locked = log_exporter.battery_status.get("locked_working", False)
        socketio.emit('battery_data', {
            "data": data,
            "working": working,
            "locked_working": locked,
            "message": message,
        })
    battery.poll_forever(interval=1.5, on_update=on_update)


def pushbutton_monitor_loop():
    def on_update(payload):
        log_exporter.set_pushbutton_status(payload["status"])
        socketio.emit('button_status', payload)
    pushbutton.run_forever(on_update)


def start_monitoring():
    global _status_thread_started
    if _status_thread_started:
        return
    _status_thread_started = True
    threading.Thread(target=status_bar_monitor, daemon=True).start()
    threading.Thread(target=charger_poll_loop, daemon=True).start()
    threading.Thread(target=battery_poll_loop, daemon=True).start()
    threading.Thread(target=pushbutton_monitor_loop, daemon=True).start()


# ========== FLASK ROUTES: TESTER INFO / HOME ==========
@app.route('/')
def home():
    if not tester_info_submitted:
        return redirect(url_for('tester_info'))
    return render_template('index.html')


@app.route('/tester_info')
def tester_info():
    return render_template('tester_info.html')


@app.route('/submittestinfo', methods=['POST'])
def submittestinfo():
    global tester_info_submitted, testername, pcbserial, modelnumber, projectdetail
    testername = request.form.get('testername')
    pcbserial = request.form.get('serialnumber')
    modelnumber = request.form.get('modelnumber')
    projectdetail = request.form.get('projectdetail')

    log_exporter.set_test_details(
        testername=testername, pcbserial=pcbserial,
        modelnumber=modelnumber, projectdetail=projectdetail
    )
    tester_info_submitted = True
    start_monitoring()
    return redirect(url_for('home'))


@app.route('/read_sensors')
def read_sensors():
    return get_temp_hum()


@app.route('/system/hw_status')
def system_hw_status():
    """Lets the UI know whether the real Charger/Battery driver packages are installed at all."""
    return jsonify({
        "charger_available": charger.available,
        "battery_available": battery.available,
        "pushbutton_available": pushbutton._available,
    })


# ========== INSPECTION TAB ==========
@app.route('/save_inspection', methods=['POST'])
def save_inspection():
    data = request.get_json() or {}
    visual = data.get("visual", "no")
    electrical = data.get("electrical", "no")
    log_exporter.set_inspection(visual, electrical)
    return jsonify({"status": "success", "message": "Inspection saved."})


# ========== CHARGER TAB ==========
@app.route('/charger/read')
def charger_read():
    """Forces a fresh CAN read (blocking) - used by the tab's manual 'Test Charger' button."""
    data = charger.read_data()
    working, message = ChargerInterface.is_working(data)
    log_exporter.set_charger_status(data, working, message)
    return jsonify({"data": data, "working": working, "message": message})


@app.route('/charger/last')
def charger_last():
    data = charger.get_last()
    working, message = ChargerInterface.is_working(data)
    return jsonify({"data": data, "working": working, "message": message})


# ========== BATTERY TAB ==========
@app.route('/battery/read')
def battery_read():
    data = battery.read_data()
    working, message = BatteryInterface.is_working(data)
    log_exporter.set_battery_status(data, working, message)
    locked = log_exporter.battery_status.get("locked_working", False)
    return jsonify({"data": data, "working": working, "locked_working": locked, "message": message})


@app.route('/battery/last')
def battery_last():
    data = battery.get_last()
    working, message = BatteryInterface.is_working(data)
    locked = log_exporter.battery_status.get("locked_working", False)
    return jsonify({"data": data, "working": working, "locked_working": locked, "message": message})


# ========== DC OUTPUT TAB ==========
@app.route('/dc_out/save_port', methods=['POST'])
def dc_out_save_port():
    data = request.get_json() or {}
    port = data.get("port")
    result = data.get("result")
    if port not in ("port1", "port2", "port3") or result not in ("pass", "fail"):
        return jsonify({"status": "error", "message": "Invalid port or result"}), 400
    log_exporter.set_dc_out_port(port, result)
    return jsonify({"status": "success"})


@app.route('/dc_out/backup/start', methods=['POST'])
def dc_out_backup_start():
    """
    Operator confirms AC/charger has physically been switched off.
    Blocks (in a worker thread via SocketIO's threading mode) while polling
    the battery for the Discharging / Disconnected state, up to ~20s.
    """
    global _backup_test_running
    payload = request.get_json() or {}
    confirmed_off = bool(payload.get("confirmed_off", False))

    if not confirmed_off:
        return jsonify({
            "status": "waiting",
            "message": "Please turn off the charger output / remove AC input, then confirm."
        })

    with _backup_test_lock:
        if _backup_test_running:
            return jsonify({"status": "error", "message": "Backup test already running."}), 409
        _backup_test_running = True

    try:
        result = poll_for_discharge(battery, timeout_s=20.0, interval_s=1.0)
    finally:
        with _backup_test_lock:
            _backup_test_running = False

    log_exporter.set_backup_test(result)
    return jsonify({"status": "success", "result": result})


# ========== QC / DEVICE INFO ==========
@app.route('/get_test_info')
def get_test_info():
    return jsonify(log_exporter.test_details)


@app.route('/get_last_log')
def get_last_log():
    return jsonify(log_exporter.get_last_log())


@app.route('/qc_status', methods=['POST'])
def qc_status():
    data = request.get_json() or {}
    status = data.get("qc_status", "FAILED")
    log_exporter.set_qc_status(status)
    return jsonify({"status": "success", "qc_status": status})


@app.route('/write_eeprom_full', methods=['POST'])
def write_eeprom_full():
    try:
        payload = request.get_json() or {}
        uuid = payload.get("uuid", "UNKNOWN")
        hw = payload.get("hw", "UNKNOWN")
        timestamp = payload.get("timestamp") or datetime.now().isoformat()
        qc_status_val = payload.get("qc_status", "FAILED")
        qc_reasons = payload.get("qc_fail_reasons", [])
        full_log = payload.get("full_log")

        device_info = {
            "UUID": uuid,
            "HW": hw,
            "timestamp": timestamp,
            "qc_status": qc_status_val,
        }

        if not full_log:
            full_log = log_exporter.get_last_log()
        full_log["qc_status"] = qc_status_val
        if qc_reasons:
            full_log["qc_fail_reasons"] = qc_reasons

        combined = {"device_info": device_info, "log_report": full_log}
        combined_bytes = json.dumps(combined, default=str).encode("utf-8")

        window_size = EEPROM_WINDOW_END - EEPROM_WINDOW_START
        if len(combined_bytes) > window_size:
            return jsonify({
                "status": "error",
                "message": f"Combined log ({len(combined_bytes)}B) exceeds EEPROM window ({window_size}B). "
                            f"Trim the log or widen EEPROM_WINDOW_END in config.py."
            }), 400

        _clear_eeprom_range(EEPROM_WINDOW_START, EEPROM_WINDOW_END)

        addr = EEPROM_WINDOW_START
        idx = 0
        while idx < len(combined_bytes):
            chunk = list(combined_bytes[idx: idx + EEPROM_PAGE_SIZE])
            eeprom.write_eeprom(addr, chunk)
            addr += len(chunk)
            idx += EEPROM_PAGE_SIZE

        written_len = len(combined_bytes)
        if written_len < window_size:
            pad_len = window_size - written_len
            eeprom.write_eeprom(EEPROM_WINDOW_START + written_len, [0xFF] * pad_len)

        return jsonify({
            "status": "success",
            "message": "EEPROM written successfully",
            "device_info": device_info,
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/device_info')
def device_info():
    try:
        window_size = EEPROM_WINDOW_END - EEPROM_WINDOW_START
        raw = eeprom.read_eeprom(EEPROM_WINDOW_START, window_size)
        cleaned = safe_clean(raw)

        if not cleaned:
            return jsonify({"status": "success", "device_info": {}, "log_report": {}})

        try:
            combined = json.loads(cleaned.decode("utf-8"))
        except Exception as e:
            return jsonify({"status": "success", "device_info": {"error": f"Invalid JSON: {e}"}, "log_report": {}})

        return jsonify({
            "status": "success",
            "device_info": combined.get("device_info", {}),
            "log_report": combined.get("log_report", {}),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ========== MQTT CONFIG / EXPORT ==========
@app.route('/get_mqtt_config')
def get_mqtt_config():
    return jsonify(mqtt_client.mqtt_config)


@app.route('/update_mqtt', methods=['POST'])
def update_mqtt():
    config = request.json
    mqtt_client.update_config(config)
    return jsonify({"message": "MQTT configuration updated!"})


@socketio.on('export_log')
def export_log():
    log_exporter.export_log()


@socketio.on('qc_status_update')
def handle_qc_status_update(data):
    qc_status_val = data.get('qc_status', 'FAILED')
    qc_fail_reasons = data.get('qc_fail_reasons', [])
    log_exporter.set_qc_status(qc_status_val, qc_fail_reasons)
    print(f"QC Status Updated: {qc_status_val} - Reasons: {qc_fail_reasons}")


# ========== ENTRYPOINT ==========
if __name__ == '__main__':
    mqtt_client.connect_mqtt()
    start_monitoring()
    print("EMC PDU Testbench starting on :5000")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
