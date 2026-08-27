from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import datetime, timezone

import psutil
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_socketio import SocketIO

from log_exporter import LogExporter
from sensor_reader import get_temp_hum

try:
    from eeprom import EEPROM
except Exception:  # pragma: no cover - non-BBB hosts
    EEPROM = None

try:
    from Battery.qhb import CAN_QHB
except Exception:  # pragma: no cover - if CAN libs are unavailable
    CAN_QHB = None

try:
    from Charger.NPB import NPB_Charger
except Exception:  # pragma: no cover - if CAN libs are unavailable
    NPB_Charger = None

app = Flask(__name__)
app.config["SECRET_KEY"] = "emc-pdu-testbench"
socketio = SocketIO(app, cors_allowed_origins="*")

log_exporter = LogExporter()

eeprom = EEPROM() if EEPROM is not None else None
battery = CAN_QHB() if CAN_QHB is not None else None
charger = NPB_Charger(channel="can1", address=0x03) if NPB_Charger is not None else None

status_state = {
    "cpu": 0,
    "can_uplink": "DOWN",
    "temp": "--",
    "hum": "--",
    "eeprom": "ERROR",
    "mqtt": "DOWN",
    "timestamp": "--",
    "battery_state": "--",
    "charger_connected": "--",
    "charger_vout": "--",
    "charger_iout": "--",
    "charger_temp": "--",
}

tester_info_submitted = False


def detect_can_uplink() -> str:
    try:
        return "UP" if os.path.exists("/sys/class/net/can0") or os.path.exists("/sys/class/net/can1") else "DOWN"
    except Exception:
        return "DOWN"


def detect_eeprom_status() -> str:
    try:
        return "GOOD" if os.path.exists("/dev/i2c-2") else "ERROR"
    except Exception:
        return "ERROR"


def detect_mqtt_status() -> str:
    try:
        host = "127.0.0.1"
        port = 1883
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex((host, port))
        s.close()
        return "UP" if result == 0 else "DOWN"
    except Exception:
        return "DOWN"


def read_battery_snapshot():
    if battery is None:
        return {}
    try:
        if battery.bus is None:
            battery.init_device()
        data = battery.read_data()
        pdu = data.get("pdu_batt", {}) if isinstance(data, dict) else {}
        basic = pdu.get("batt_basic", {})
        if basic:
            return {
                "battery_state": basic.get("batt_state", "--"),
                "charger_connected": basic.get("batt_charger", "--"),
                "battery_soc": basic.get("batt_soc", "--"),
                "battery_voltage": basic.get("batt_voltage", "--"),
                "battery_current": basic.get("batt_current", "--"),
            }
    except Exception:
        pass
    return {}


def read_charger_snapshot():
    if charger is None:
        return {}
    try:
        if not getattr(charger, "charger_initialized", False):
            charger.start_device()
        data = charger.read_data()
        pdu = data.get("pdu_chgr", {}) if isinstance(data, dict) else {}
        return {
            "charger_connected": "connected" if pdu.get("chgr_model_name") else "disconnected",
            "charger_vout": pdu.get("chgr_vout_DC", "--"),
            "charger_iout": pdu.get("chgr_iout", "--"),
            "charger_temp": pdu.get("chgr_temp", "--"),
            "charger_error": pdu.get("chgr_error", {}),
        }
    except Exception:
        return {}


def status_loop():
    while True:
        temp_hum = get_temp_hum()
        battery_snapshot = read_battery_snapshot()
        charger_snapshot = read_charger_snapshot()

        status_state["cpu"] = psutil.cpu_percent(interval=None)
        status_state["temp"] = temp_hum.get("temperature", "--")
        status_state["hum"] = temp_hum.get("humidity", "--")
        status_state["can_uplink"] = detect_can_uplink()
        status_state["eeprom"] = detect_eeprom_status()
        status_state["mqtt"] = detect_mqtt_status()
        status_state["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if battery_snapshot:
            status_state["battery_state"] = battery_snapshot.get("battery_state", "--")
            status_state["charger_connected"] = battery_snapshot.get("charger_connected", "--")
        else:
            status_state["battery_state"] = status_state.get("battery_state", "--")
            status_state["charger_connected"] = status_state.get("charger_connected", "--")

        if charger_snapshot:
            status_state["charger_vout"] = charger_snapshot.get("charger_vout", "--")
            status_state["charger_iout"] = charger_snapshot.get("charger_iout", "--")
            status_state["charger_temp"] = charger_snapshot.get("charger_temp", "--")

        log_exporter.set_environment_data(status_state["temp"], status_state["hum"], status_state["cpu"])
        log_exporter.set_status_summary(status_state["can_uplink"], status_state["eeprom"], status_state["mqtt"])
        socketio.emit("status_update", status_state)
        time.sleep(2)


def start_status_monitor():
    threading.Thread(target=status_loop, daemon=True).start()


@app.route("/")
def home():
    global tester_info_submitted
    if not tester_info_submitted:
        return redirect(url_for("tester_info"))
    return render_template("index.html")


@app.route("/tester_info")
def tester_info():
    return render_template("tester_info.html")


@app.route("/submittestinfo", methods=["POST"])
def submittestinfo():
    global tester_info_submitted
    tester_info_submitted = True
    tester = {
        "testername": request.form.get("testername", "UNKNOWN"),
        "serialnumber": request.form.get("serialnumber", "UNKNOWN"),
        "modelnumber": request.form.get("modelnumber", "UNKNOWN"),
        "projectdetail": request.form.get("projectdetail", "UNKNOWN"),
    }
    log_exporter.set_test_details(**tester)
    return redirect(url_for("home"))


@app.route("/read_status")
def read_status():
    return jsonify(status_state)


@app.route("/save_inspection", methods=["POST"])
def save_inspection():
    payload = request.get_json() or {}
    log_exporter.set_inspection(payload)
    return jsonify({"status": "success", "message": "Inspection saved"})


@app.route("/save_charger_result", methods=["POST"])
def save_charger_result():
    payload = request.get_json() or {}
    log_exporter.set_charger(payload)
    return jsonify({"status": "success", "message": "Charger details saved"})


@app.route("/save_battery_result", methods=["POST"])
def save_battery_result():
    payload = request.get_json() or {}
    log_exporter.set_battery(payload)
    return jsonify({"status": "success", "message": "Battery details saved"})


@app.route("/save_dc_output", methods=["POST"])
def save_dc_output():
    payload = request.get_json() or {}
    log_exporter.set_dc_output(payload)
    return jsonify({"status": "success", "message": "DC output details saved"})


@app.route("/get_last_log")
def get_last_log():
    return jsonify(log_exporter.get_last_log())


@app.route("/device_info")
def device_info():
    try:
        state_path = os.path.join(os.path.dirname(__file__), "eeprom_data.json")
        if not os.path.exists(state_path):
            return jsonify({"status": "success", "device_info": {}, "log_report": log_exporter.get_last_log()})
        with open(state_path, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        return jsonify({"status": "success", "device_info": saved.get("device_info", {}), "log_report": saved.get("log_report", {})})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)})


@app.route("/write_eeprom_full", methods=["POST"])
def write_eeprom_full():
    payload = request.get_json() or {}
    device_info = {
        "testername": log_exporter.log.get("tester-info", {}).get("testername", "UNKNOWN"),
        "serialnumber": log_exporter.log.get("tester-info", {}).get("serialnumber", "UNKNOWN"),
        "modelnumber": log_exporter.log.get("tester-info", {}).get("modelnumber", "UNKNOWN"),
        "projectdetail": log_exporter.log.get("tester-info", {}).get("projectdetail", "UNKNOWN"),
        "timestamp": payload.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "qc_status": payload.get("qc_status", "FAILED"),
    }
    full_log = payload.get("full_log") or log_exporter.get_last_log()
    final_data = {"device_info": device_info, "log_report": full_log}
    target = os.path.join(os.path.dirname(__file__), "eeprom_data.json")
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(final_data, fh, indent=2)
    return jsonify({"status": "success", "device_info": device_info, "log_report": full_log})


@app.route("/export_log")
def export_log():
    export_payload = {
        "event": "pdu-test-export",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": log_exporter.get_last_log(),
    }
    out_path = os.path.join(os.path.dirname(__file__), "exported_log.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(export_payload, fh, indent=2)
    return jsonify({"status": "success", "message": "Log exported", "file": out_path})


if __name__ == "__main__":
    start_status_monitor()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
