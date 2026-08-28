"""
Charger interface adapter for the EMC PDU Testbench.

Per project note: this app must NOT re-implement the Mean Well NPB-1200
CAN driver stack - that already exists in the PDU firmware project
(`charger_address.py`, `can_communication.py`, `NPB1200_Charger.py`,
node address 0x03 on can1 @ 250 kbps, 29-bit extended frames). This
module only imports and wraps that existing driver.

To wire it up for real:
    Drop charger_address.py, can_communication.py and NPB1200_Charger.py
    from the PDU firmware repo into this project's root (same folder as
    app.py). Nothing else needs to change - the import at the top of
    this file will pick them up automatically and _HARDWARE_AVAILABLE
    will flip to True.

Until those files are present, ChargerInterface transparently runs in
mock mode so the rest of the testbench (UI, logging, QC, EEPROM) can
still be built and demoed without a CAN bus attached.

Expected read_data() shape from NPB1200_Charger (per the locked-in PDU
firmware architecture - inline JSON assembly, no zero-code pollution on
success, fault fields only emitted on real faults):

    {
        "vout": 53.5,
        "iout": 4.2,
        "temp": 38.1
        # "gdr_error": {"code": "CAN00x", "message": "..."}   <- only on fault
    }
"""
import random
import threading
import time

from config import CAN_CHANNEL, FORCE_MOCK

_HARDWARE_AVAILABLE = False
if not FORCE_MOCK:
    try:
        from can_communication import CANCommunication
        from charger_address import ChargerAddress
        from NPB1200_Charger import NPB1200_Charger
        _HARDWARE_AVAILABLE = True
    except ImportError:
        _HARDWARE_AVAILABLE = False


class ChargerInterface:
    def __init__(self, can_channel: str = CAN_CHANNEL, mock: bool = None):
        self.mock = (not _HARDWARE_AVAILABLE) if mock is None else mock
        self._lock = threading.Lock()
        self._last_data = {}

        if not self.mock:
            try:
                self._bus = CANCommunication(channel=can_channel)
                self._charger = NPB1200_Charger(self._bus, ChargerAddress())
            except Exception as e:
                print(f"ChargerInterface: falling back to mock mode ({e})")
                self.mock = True

        if self.mock:
            print("ChargerInterface: running in MOCK mode "
                  "(drop in charger_address.py / can_communication.py / "
                  "NPB1200_Charger.py from the PDU firmware repo for real hardware)")

    def read_data(self) -> dict:
        """Force a fresh read from the charger. Blocking CAN I/O - call from a worker thread."""
        if self.mock:
            data = self._mock_read()
        else:
            try:
                data = self._charger.read_data()
            except Exception as e:
                data = {"gdr_error": {"code": "CAN001", "message": f"charger read failed: {e}"}}

        with self._lock:
            self._last_data = data
        return data

    def get_last(self) -> dict:
        """Non-blocking - returns the most recent poll result."""
        with self._lock:
            return dict(self._last_data)

    def poll_forever(self, interval: float = 1.0, on_update=None, stop_event: threading.Event = None):
        """Run in a daemon thread; mirrors the battery_poll_task() pattern in the firmware."""
        while stop_event is None or not stop_event.is_set():
            data = self.read_data()
            if on_update:
                on_update(data)
            time.sleep(interval)

    @staticmethod
    def is_working(data: dict) -> tuple[bool, str]:
        """Returns (working, message) - 'good' unless a gdr_error fault is present."""
        if not data:
            return False, "No data received from charger"
        if "gdr_error" in data:
            err = data["gdr_error"]
            return False, f"{err.get('code', 'ERR')}: {err.get('message', 'unknown fault')}"
        return True, "Charger interface working"

    # ---------------- mock data source ----------------
    def _mock_read(self) -> dict:
        return {
            "vout": round(53.5 + random.uniform(-0.2, 0.2), 2),
            "iout": round(4.2 + random.uniform(-0.4, 0.4), 2),
            "temp": round(38.0 + random.uniform(-1.0, 1.0), 1),
        }
