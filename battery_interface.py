"""
Battery interface adapter for the EMC PDU Testbench.

Same principle as charger_interface.py: this does NOT re-implement the
QHB battery CAN driver - it wraps the existing `qhb.py` module already
built for the PDU firmware stack (batt_basic / batt_advance sub-objects,
_calc_runtime_minutes() helper, gdr_error-style fault codes).

To wire it up for real:
    Drop qhb.py from the PDU firmware repo into this project's root.
    The import below will pick it up automatically.

Expected read_data() shape from qhb.py:

    {
        "batt_basic": {
            "voltage": 52.1,
            "current": -3.2,
            "soc": 87,
            "battery_state": "Ready" | "Charging" | "Discharging",
            "charger_connected": true | false
        },
        "batt_advance": {
            "cell_voltages": [...],
            "temperature": 29.4,
            "runtime_minutes": 42,
            ...
        }
        # "gdr_error": {"code": "CAN00x", "message": "..."}   <- only on fault
    }

`battery_state` and `charger_connected` (inside batt_basic) are exactly
the two fields backup_logic.py needs to evaluate the AC/Battery backup
truth table, so keep those field names stable in qhb.py.
"""
import random
import threading
import time

from config import CAN_CHANNEL, FORCE_MOCK

_HARDWARE_AVAILABLE = False
if not FORCE_MOCK:
    try:
        from can_communication import CANCommunication
        from charger_address import ChargerAddress  # battery shares the CAN bus / addressing scheme
        from qhb import QHBBattery
        _HARDWARE_AVAILABLE = True
    except ImportError:
        _HARDWARE_AVAILABLE = False


class BatteryInterface:
    def __init__(self, can_channel: str = CAN_CHANNEL, mock: bool = None):
        self.mock = (not _HARDWARE_AVAILABLE) if mock is None else mock
        self._lock = threading.Lock()
        self._last_data = {}
        # mock-mode only: lets the UI "simulate" AC being removed so the
        # battery-backup test can be exercised without real hardware
        self._mock_ac_present = True

        if not self.mock:
            try:
                self._bus = CANCommunication(channel=can_channel)
                self._battery = QHBBattery(self._bus, ChargerAddress())
            except Exception as e:
                print(f"BatteryInterface: falling back to mock mode ({e})")
                self.mock = True

        if self.mock:
            print("BatteryInterface: running in MOCK mode "
                  "(drop in qhb.py from the PDU firmware repo for real hardware)")

    def read_data(self) -> dict:
        if self.mock:
            data = self._mock_read()
        else:
            try:
                data = self._battery.read_data()
            except Exception as e:
                data = {"gdr_error": {"code": "CAN002", "message": f"battery read failed: {e}"}}

        with self._lock:
            self._last_data = data
        return data

    def get_last(self) -> dict:
        with self._lock:
            return dict(self._last_data)

    def poll_forever(self, interval: float = 1.0, on_update=None, stop_event: threading.Event = None):
        while stop_event is None or not stop_event.is_set():
            data = self.read_data()
            if on_update:
                on_update(data)
            time.sleep(interval)

    @staticmethod
    def is_working(data: dict) -> tuple[bool, str]:
        """Battery interface counts as 'working' once batt_basic is present and charger shows connected."""
        if not data:
            return False, "No data received from battery"
        if "gdr_error" in data:
            err = data["gdr_error"]
            return False, f"{err.get('code', 'ERR')}: {err.get('message', 'unknown fault')}"
        basic = data.get("batt_basic")
        if not basic:
            return False, "batt_basic missing from battery response"
        if not basic.get("charger_connected"):
            return False, "batt_basic present but charger_connected is False"
        return True, "Battery interface working"

    # ---------------- mock-mode control (dev/UI only) ----------------
    def set_mock_ac_present(self, present: bool):
        """Used by the DC-out tab's 'simulate AC removed' control in mock mode."""
        self._mock_ac_present = present

    # ---------------- mock data source ----------------
    def _mock_read(self) -> dict:
        if self._mock_ac_present:
            state = "Ready"
            charger_connected = True
            current = 0.4
        else:
            state = "Discharging"
            charger_connected = False
            current = -3.1

        return {
            "batt_basic": {
                "voltage": round(52.0 + random.uniform(-0.3, 0.3), 2),
                "current": current,
                "soc": 87,
                "battery_state": state,
                "charger_connected": charger_connected,
            },
            "batt_advance": {
                "cell_voltages": [round(3.25 + random.uniform(-0.02, 0.02), 3) for _ in range(16)],
                "temperature": round(29.0 + random.uniform(-1, 1), 1),
                "runtime_minutes": 42 if state == "Discharging" else None,
            },
        }
