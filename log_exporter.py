"""
Central in-memory test-session log for the PDU testbench.

Same role as the ACU testbench's LogExporter (single object accumulating
results as the operator moves through tabs, then flattened to JSON for
the QC report / EEPROM write / MQTT export) - schema changed to match
the PDU's four tabs (Inspection, Charger, Battery, DC Out) instead of
the ACU's gas/badge/alarm/indicator tabs.
"""
import time


class LogExporter:
    def __init__(self, mqtt_client):
        self.mqtt_client = mqtt_client

        self.test_details = {}
        self.env_data = {"cpu": None, "temperature": None, "humidity": None}

        self.inspection = {"visual": "not tested", "electrical": "not tested"}

        self.charger_status = {"data": {}, "working": None, "message": "not tested"}
        self.battery_status = {
            "data": {},
            "working": None,
            "message": "not tested",
            "locked_working": False,
        }
        self.indicator_status = {
            "pushbutton": "not tested",
            "rgb_led": {
                "red": "not tested",
                "green": "not tested",
                "blue": "not tested",
            },
            "rgb_led_status": "error",
        }

        self.dc_out = {
            "port1": "not tested",
            "port2": "not tested",
            "port3": "not tested",
        }
        self.backup_test = {
            "requested": False,
            "confirmed_off_by_operator": None,
            "result": "not tested",
            "observed_battery_state": None,
            "observed_charger_connected": None,
        }

        self.can_status = {"state": "UNKNOWN", "health": "ERROR", "detail": ""}
        self.eeprom_status = {"present": None}
        self.mqtt_status = {"connected": False, "reachable": None}

        self.qc_status = "NOT_RUN"
        self.qc_fail_reasons = []

    # ---------------- setters ----------------
    def set_test_details(self, testername, pcbserial, modelnumber=None, projectdetail=None):
        self.test_details = {
            "testername": testername,
            "pcbserial": pcbserial,
            "modelnumber": modelnumber,
            "projectdetail": projectdetail,
        }

    def set_environment_data(self, temperature, humidity, cpu):
        self.env_data = {"temperature": temperature, "humidity": humidity, "cpu": cpu}

    def set_inspection(self, visual, electrical):
        self.inspection = {"visual": visual, "electrical": electrical}

    def set_charger_status(self, data, working, message):
        self.charger_status = {"data": data, "working": working, "message": message}

    def set_battery_status(self, data, working, message):
        locked = bool(self.battery_status.get("locked_working", False))
        if working:
            locked = True

        if locked and not working:
            message = "Battery interface working (latched)"
            working = True

        self.battery_status = {
            "data": data,
            "working": bool(working),
            "message": message,
            "locked_working": locked,
        }

    def set_pushbutton_status(self, status):
        self.indicator_status["pushbutton"] = status

    def set_indicator(self, key, value, color=None):
        if key == "pushbutton":
            self.indicator_status["pushbutton"] = value
        elif key == "rgb_led" and color:
            self.indicator_status["rgb_led"][color] = value
            rgb = self.indicator_status["rgb_led"]
            self.indicator_status["rgb_led_status"] = "working" if all(
                rgb.get(color_name) == "working" for color_name in ["red", "green", "blue"]
            ) else "error"

    def set_dc_out_port(self, port_key, result):
        if port_key in self.dc_out:
            self.dc_out[port_key] = result

    def set_backup_test(self, result_dict):
        self.backup_test.update(result_dict)

    def set_can_status(self, status_dict):
        self.can_status = status_dict

    def set_eeprom_status(self, present):
        self.eeprom_status = {"present": present}

    def set_mqtt_status(self, connected, reachable):
        self.mqtt_status = {"connected": connected, "reachable": reachable}

    def set_qc_status(self, status, reasons=None):
        self.qc_status = status
        self.qc_fail_reasons = reasons or []

    # ---------------- readers ----------------
    def get_last_log(self):
        return {
            "test_details": self.test_details,
            "system-check": {
                "cpu-usage": self.env_data["cpu"],
                "temperature": self.env_data["temperature"],
                "humidity": self.env_data["humidity"],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "inspection-status": self.inspection,
            "charger-status": self.charger_status,
            "battery-status": self.battery_status,
            "dc-output-status": self.dc_out,
            "battery-backup-status": self.backup_test,
            "can-status": self.can_status,
            "eeprom-status": self.eeprom_status,
            "mqtt-status": self.mqtt_status,
            "indicator-status": self.indicator_status,
            "qc_status": self.qc_status,
            "qc_fail_reasons": self.qc_fail_reasons,
        }

    def export_log(self):
        data = self.get_last_log()
        self.mqtt_client.publish_data(data)
        return data
