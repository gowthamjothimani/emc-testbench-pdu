import threading
import time
from config import CAN_CHANNEL, CHARGER_NODE_ADDRESS
from Charger.NPB import NPB_Charger

def _na_payload(code: str, message: str) -> dict:
    return {
        "pdu_chgr": {
            "timestamp": None,
            "chgr_model_name": "",
            "chgr_vout_DC": None,
            "chgr_iout": None,
            "chgr_temp": None,
            "chgr_error": {"chgr_error_message": message, "chgr_error_code": code},
        }
    }

class ChargerInterface:
    def __init__(self, can_channel: str = CAN_CHANNEL, address: int = CHARGER_NODE_ADDRESS):
        self._lock = threading.Lock()
        self._last_data = {}
        self.available = NPB_Charger is not None

        if not self.available:
            self._charger = None
            return

        self._charger = NPB_Charger(channel=can_channel, address=address)
        try:
            self._charger.start_device()
        except Exception as e:
            print(f"ChargerInterface: start_device() failed during initialization: {e}")

    def read_data(self) -> dict:
        if not self.available:
            data = _na_payload("NO_DRIVER", "Charger driver not installed - see Charger/NPB.py")
        else:
            try:
                if not getattr(self._charger, "charger_initialized", False):
                    self._charger.start_device()
                data = self._charger.read_data()
                print(f"ChargerInterface: read_data() returned: {data}")
            except Exception as e:
                data = _na_payload("CAN_ADAPTER_ERROR", f"Unexpected charger adapter error: {e}")

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
        chgr = (data or {}).get("pdu_chgr")
        if not chgr:
            return False, "No data received from charger (NA)"

        err = chgr.get("chgr_error")
        if err:
            if isinstance(err, dict) and (err.get("chgr_error_code") or err.get("chgr_error_message")):
                return False, f"{err.get('chgr_error_code', 'ERR')}: {err.get('chgr_error_message', 'unknown fault')}"
            return False, "Charger returned an error state"

        has_value = any(
            chgr.get(key) not in (None, "", 0.0, 0)
            for key in ("chgr_vout_DC", "chgr_iout", "chgr_temp", "chgr_vin_AC")
        )
        if not has_value:
            return False, "No charger telemetry received"

        return True, "Charger interface working"
