from __future__ import annotations

from typing import Any, Dict, List


class LogExporter:
    def __init__(self):
        self.log: Dict[str, Any] = {
            "tester-info": {"testername": "UNKNOWN", "serialnumber": "UNKNOWN", "modelnumber": "UNKNOWN", "projectdetail": "UNKNOWN"},
            "system-check": {"cpu-usage": 0, "temperature": "--", "humidity": "--", "can-uplink": "DOWN", "eeprom-status": "ERROR", "mqtt-status": "DOWN"},
            "board-inspection-status": {"visual": "not tested", "electrical": "not tested"},
            "charger": {"vout": "--", "iout": "--", "temp": "--", "interface_status": "not tested", "message": "--"},
            "battery": {"battery_state": "not tested", "charger_connected": "not tested", "status": "not tested", "power_source": "not tested", "power_off_confirmed": "not tested"},
            "dc-output": {"port_1": "not tested", "port_2": "not tested", "port_3": "not tested", "battery_backup": "not tested", "notes": ""},
            "qc-status": {"status": "NOT RUN", "fail_reasons": []},
        }

    def set_test_details(self, **kwargs):
        tester = self.log["tester-info"]
        for key, value in kwargs.items():
            if value is not None:
                tester[key] = value

    def set_environment_data(self, temp, hum, cpu):
        self.log["system-check"]["temperature"] = temp
        self.log["system-check"]["humidity"] = hum
        self.log["system-check"]["cpu-usage"] = cpu

    def set_status_summary(self, can_uplink: str, eeprom_status: str, mqtt_status: str):
        self.log["system-check"]["can-uplink"] = can_uplink
        self.log["system-check"]["eeprom-status"] = eeprom_status
        self.log["system-check"]["mqtt-status"] = mqtt_status

    def set_inspection(self, payload):
        self.log["board-inspection-status"] = {
            "visual": payload.get("visual", "no"),
            "electrical": payload.get("electrical", "no"),
        }

    def set_charger(self, payload):
        self.log["charger"] = {
            "vout": payload.get("vout", "--"),
            "iout": payload.get("iout", "--"),
            "temp": payload.get("temp", "--"),
            "interface_status": payload.get("interface_status", "not tested"),
            "message": payload.get("message", "--"),
        }

    def set_battery(self, payload):
        self.log["battery"] = {
            "battery_state": payload.get("battery_state", "not tested"),
            "charger_connected": payload.get("charger_connected", "not tested"),
            "status": payload.get("status", "not tested"),
            "power_source": payload.get("power_source", "not tested"),
            "power_off_confirmed": payload.get("power_off_confirmed", "not tested"),
        }

    def set_dc_output(self, payload):
        self.log["dc-output"] = {
            "port_1": payload.get("port_1", "not tested"),
            "port_2": payload.get("port_2", "not tested"),
            "port_3": payload.get("port_3", "not tested"),
            "battery_backup": payload.get("battery_backup", "not tested"),
            "notes": payload.get("notes", ""),
        }

    def evaluate_qc(self) -> Dict[str, Any]:
        failed: List[str] = []
        ok_guidance = {
            "visual": self.log["board-inspection-status"].get("visual") == "yes",
            "electrical": self.log["board-inspection-status"].get("electrical") == "yes",
            "charger": self.log["charger"].get("interface_status") == "good",
            "battery": self.log["battery"].get("charger_connected") == "connected" and self.log["battery"].get("battery_state") in {"charging", "discharging"},
            "dc-output": self.log["dc-output"].get("battery_backup") in {"pass", "yes"},
        }
        for key, is_ok in ok_guidance.items():
            if not is_ok:
                failed.append(f"{key} failed")
        qc_status = "PASSED" if not failed else "FAILED"
        self.log["qc-status"] = {"status": qc_status, "fail_reasons": failed}
        return self.log["qc-status"]

    def get_last_log(self):
        return self.log
