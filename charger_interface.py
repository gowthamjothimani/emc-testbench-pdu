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

    def read_data(self) -> dict:
        if not self.available:
            data = _na_payload("NO_DRIVER", "Charger driver not installed - see Charger/NPB.py")
        else:
            try:
                data = self._charger.read_data()
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
            return False, f"{err.get('chgr_error_code', 'ERR')}: {err.get('chgr_error_message', 'unknown fault')}"
        return True, "Charger interface working"
