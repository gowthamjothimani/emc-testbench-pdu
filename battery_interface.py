import threading
import time
from config import CAN_CHANNEL
from Battery.qhb import CAN_QHB


def _na_payload(code: str, message: str) -> dict:
    return {
        "pdu_batt": {
            "timestamp": None,
            "batt_name": "PDU Battery",
            "batt_status": "inactive",
            "batt_basic": {},
            "batt_advance": {},
            "batt_error": {
                "success": False,
                "status": code,
                "device_type": "QHB_BATTERY",
                "error_code": code,
                "error_message": message,
            },
        }
    }


class BatteryInterface:
    def __init__(self, can_channel: str = CAN_CHANNEL):
        self._lock = threading.Lock()
        self._last_data = {}
        self.available = CAN_QHB is not None
        self._listener_started = False

        if not self.available:
            print(f"BatteryInterface: Battery driver package not importable ({_IMPORT_ERROR}). "
                  f"Battery tab will report NA until Battery/qhb.py etc. are in place.")
            self._battery = None
            return

        self._battery = CAN_QHB()
        self._battery.channel = can_channel

        if self._battery.init_device():
            self._start_listener_thread()
        else:
            print("BatteryInterface: init_device() failed - CAN1 not reachable. "
                  "Will keep reporting NA; retrying init on next read.")

    def _start_listener_thread(self):
        if self._listener_started:
            return
        self._listener_started = True
        threading.Thread(target=self._battery.start_device, daemon=True).start()

    def read_data(self) -> dict:
        if not self.available:
            data = _na_payload("NO_DRIVER", "Battery driver not installed - see Battery/qhb.py")
        else:
            # Retry init_device()
            if not self._listener_started and self._battery.bus is None:
                if self._battery.init_device():
                    self._start_listener_thread()

            try:
                data = self._battery.read_data()
            except Exception as e:
                data = _na_payload("CAN_ADAPTER_ERROR", f"Unexpected battery adapter error: {e}")

        with self._lock:
            self._last_data = data
        return data

    def get_last(self) -> dict:
        with self._lock:
            return dict(self._last_data)

    def poll_forever(self, interval: float = 1.5, on_update=None, stop_event: threading.Event = None):
        while stop_event is None or not stop_event.is_set():
            data = self.read_data()
            if on_update:
                on_update(data)
            time.sleep(interval)

    @staticmethod
    def is_working(data: dict) -> tuple[bool, str]:
        batt = (data or {}).get("pdu_batt")
        if not batt:
            return False, "No data received from battery (NA)"

        err = batt.get("batt_error")
        if err:
            return False, f"{err.get('error_code', 'ERR')}: {err.get('error_message', 'unknown fault')}"

        if not batt.get("batt_basic"):
            return False, "batt_basic missing from battery response (NA)"

        return True, "Battery interface working"
