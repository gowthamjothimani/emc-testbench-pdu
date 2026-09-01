import time
import datetime
import threading
from typing import Optional, Dict, Any, List
from charger_address import ChargerAddress
from can_communication import CANCommunication, CANCommError

class NPB_Charger:
    _instances: Dict[str, "NPB_Charger"] = {}
    _lock = threading.Lock()
    _is_initialized = False

    def __new__(cls, channel: str = "can1", address: int = 0x03, *args, **kwargs):
        key = f"{channel}:0x{address:02X}"
        with cls._lock:
            if key not in cls._instances:
                instance = super().__new__(cls)
                instance._key = key
                instance._constructed = False
                cls._instances[key] = instance
            return cls._instances[key]

    def __init__(self, channel: str = "can1", address: int = 0x03,
                 bitrate: int = 250000, timeout: float = 1.0,
                 retry_count: int = 3, chgr_type: str = "1"):
        NPB_Charger._is_initialized = True
        if self._constructed:
            return

        self.channel = channel
        self.address = address
        self.bitrate = bitrate
        self.timeout = timeout
        self.retry_count = retry_count
        self.chgr_type = chgr_type

        self._initialize()
        self._constructed = True

    def _initialize(self):
        self.chargerAddress = ChargerAddress()

        tx_id = self.chargerAddress.controller_to_charger_base | (self.address & 0xFF)
        rx_id = self.chargerAddress.charger_to_controller_base | (self.address & 0xFF)

        self.comm = CANCommunication(channel=self.channel,bitrate=self.bitrate,tx_id=tx_id,rx_id=rx_id,
            default_timeout=self.timeout,
            retry_count=self.retry_count,
        )

        self.isInitialized = False
        
        # Identification
        self.chgr_model_name: str = ""
        self.chgr_serial_number: str = ""
        self.chgr_firmware_version: str = ""
        self.chgr_mfr_name: str = ""

        # Live measurements
        self.vin: Optional[float] = None
        self.vout: Optional[float] = None
        self.iout: Optional[float] = None
        self.temperature: Optional[float] = None

        # Decoded status blocks
        self.operation_state: Optional[str] = None
        self.fault_status: Dict[str, Any] = {}
        self.system_status: Dict[str, Any] = {}
        self.charger_status: Dict[str, Any] = {}

        # Communication / lifecycle state
        self.charger_initialized: bool = False
        self.success: bool = False
        self.status: str = "not_initialized"
        self.last_comm_timestamp: Optional[float] = None
        self._data_lock = threading.Lock()

    def start_device(self) -> bool:
        if not self.comm.interface_exists():
            self.success = False
            self.status = f"CAN interface '{self.channel}' not found"
            self.charger_initialized = False
            self.isInitialized = False
            print(self.status)
            return False

        if not self.comm.connect():
            self.success = False
            self.status = self.comm.last_error or "Failed to open CAN bus"
            self.charger_initialized = False
            self.isInitialized = False
            print(self.status)
            return False

        try:
            self.read_mfr_info()
            self.read_model_name()
            self.read_firmware_version()
            self.read_serial_number()

            if not self.chgr_model_name:
                self.chgr_model_name = "UNKNOWN"
            if not self.chgr_serial_number:
                self.chgr_serial_number = "UNKNOWN"
            if not self.chgr_firmware_version:
                self.chgr_firmware_version = "UNKNOWN"
            if not self.chgr_mfr_name:
                self.chgr_mfr_name = "UNKNOWN"

            self.success = True
            self.status = "initialized"
            self.charger_initialized = True
            self.isInitialized = True
            self.last_comm_timestamp = time.time()

            print(
                "Charger '%s' (SN %s) ready on %s (tx=0x%X rx=0x%X)"
                % (
                    self.chgr_model_name,
                    self.chgr_serial_number,
                    self.channel,
                    self.comm.tx_id,
                    self.comm.rx_id,
                )
            )
            return True

        except Exception as exc:
            self.success = False
            self.status = f"start_device error: {exc}"
            self.charger_initialized = False
            self.isInitialized = False
            print(self.status)
            self.comm.disconnect()
            return False

    def stop_device(self):
        self.comm.disconnect()
        self.charger_initialized = False
        self.status = "stopped"

    @staticmethod
    def _raw_to_int(raw: Optional[bytes]) -> Optional[int]:
        if raw is None:
            return None
        return int.from_bytes(raw, byteorder="little")

    @staticmethod
    def _scale(raw_int: Optional[int], factor: Optional[float]):
        if raw_int is None or factor is None:
            return raw_int
        return round(raw_int * factor, 3)

    @staticmethod
    def _to_ascii(raw: Optional[bytes]) -> str:
        if not raw:
            return ""
        return raw.split(b"\x00")[0].decode("ascii", errors="ignore").strip()

    def read_operation(self) -> Optional[str]:
        addr = self.chargerAddress
        try:
            raw = self.comm.read_command(addr.OPERATION, addr.size[addr.OPERATION])
            state = addr.operation_state_map.get(raw[0], "UNKNOWN") if raw else None
            with self._data_lock:
                self.operation_state = state
            return state
        except Exception as exc:
            print("read_operation failed: %s", exc)
            return None

    def write_operation(self, state: bool) -> bool:
        addr = self.chargerAddress
        value = addr.OPERATION_ON if state else addr.OPERATION_OFF

        ok = self.comm.write_command(addr.OPERATION, value, addr.size[addr.OPERATION])
        if not ok:
            print("write_operation: CAN write failed")
            return False

        time.sleep(0.3)  
        confirmed = self.read_operation()
        expected = "ON" if state else "OFF"

        if confirmed != expected:
            print(
                "write_operation: requested %s but readback is %s",
                expected, confirmed,
            )
            return False

        print("write_operation: charger is now %s (verified)", confirmed)
        return True

    def read_configured_output(self) -> Dict[str, Optional[float]]:
        addr = self.chargerAddress
        vraw = self.comm.read_command(addr.VOUT_SET, addr.size[addr.VOUT_SET])
        iraw = self.comm.read_command(addr.IOUT_SET, addr.size[addr.IOUT_SET])

        return {
            "vout_set": self._scale(self._raw_to_int(vraw), addr.scale[addr.VOUT_SET]),
            "iout_set": self._scale(self._raw_to_int(iraw), addr.scale[addr.IOUT_SET]),
        }

    def write_configure_voltage_current(self, vout: Optional[float] = None,
                                         iout: Optional[float] = None) -> bool:
        addr = self.chargerAddress
        write_ok = True

        if vout is not None:
            raw_val = int(round(vout / addr.scale[addr.VOUT_SET]))
            write_ok &= self.comm.write_command(addr.VOUT_SET, raw_val, addr.size[addr.VOUT_SET])

        if iout is not None:
            raw_val = int(round(iout / addr.scale[addr.IOUT_SET]))
            write_ok &= self.comm.write_command(addr.IOUT_SET, raw_val, addr.size[addr.IOUT_SET])

        if not write_ok:
            print("write_configure_voltage_current: CAN write failed")
            return False

        time.sleep(0.3)
        readback = self.read_configured_output()

        if vout is not None and readback["vout_set"] is not None:
            if abs(readback["vout_set"] - vout) > 0.5:
                print(
                    "Vout verification mismatch: requested %.2f, readback %.2f",
                    vout, readback["vout_set"],
                )
                return False

        if iout is not None and readback["iout_set"] is not None:
            if abs(readback["iout_set"] - iout) > 0.5:
                print(
                    "Iout verification mismatch: requested %.2f, readback %.2f",
                    iout, readback["iout_set"],
                )
                return False

        print("write_configure_voltage_current: verified %s", readback)
        return True

    def read_operating_data(self) -> Dict[str, Optional[float]]:
        addr = self.chargerAddress
        result: Dict[str, Optional[float]] = {}

        for reg, key in (
            (addr.READ_VIN, "vin"),
            (addr.READ_VOUT, "vout"),
            (addr.READ_IOUT, "iout"),
            (addr.READ_TEMPERATURE_1, "temperature"),
        ):
            raw = self.comm.read_command(reg, addr.size[reg])
            result[key] = self._scale(self._raw_to_int(raw), addr.scale[reg])

        with self._data_lock:
            self.vin = result["vin"]
            self.vout = result["vout"]
            self.iout = result["iout"]
            self.temperature = result["temperature"]

        return result


    def read_mfr_info(self) -> bool:
        addr = self.chargerAddress
        lo = self.comm.read_command(addr.MFR_ID_B0B5, addr.size[addr.MFR_ID_B0B5])
        hi = self.comm.read_command(addr.MFR_ID_B6B11, addr.size[addr.MFR_ID_B6B11])

        name = self._to_ascii((lo or b"") + (hi or b""))
        if not name:
            print("Failed to read manufacturer info")
            return False

        with self._data_lock:
            self.chgr_mfr_name = name
        return True

    def read_model_name(self) -> bool:
        addr = self.chargerAddress
        lo = self.comm.read_command(addr.MFR_MODEL_B0B5, addr.size[addr.MFR_MODEL_B0B5])
        hi = self.comm.read_command(addr.MFR_MODEL_B6B11, addr.size[addr.MFR_MODEL_B6B11])

        name = self._to_ascii((lo or b"") + (hi or b""))
        if not name:
            return False

        with self._data_lock:
            self.chgr_model_name = name
        return True

    def read_firmware_version(self) -> bool:
        addr = self.chargerAddress
        raw = self.comm.read_command(addr.MFR_REVISION_B0B5, addr.size[addr.MFR_REVISION_B0B5])
        version = self._to_ascii(raw)

        with self._data_lock:
            self.chgr_firmware_version = version
        return True  

    def read_serial_number(self) -> bool:
        addr = self.chargerAddress
        lo = self.comm.read_command(addr.MFR_SERIAL_B0B5, addr.size[addr.MFR_SERIAL_B0B5])
        hi = self.comm.read_command(addr.MFR_SERIAL_B6B11, addr.size[addr.MFR_SERIAL_B6B11])

        serial = self._to_ascii((lo or b"") + (hi or b""))
        if not serial:
            return False

        with self._data_lock:
            self.chgr_serial_number = serial
        return True

    def read_fault_status(self) -> Dict[str, Any]:
        addr = self.chargerAddress
        raw = self.comm.read_command(addr.FAULT_STATUS, addr.size[addr.FAULT_STATUS])
        value = self._raw_to_int(raw)

        if value is None:
            result = {"code": None, "message": "No response", "active_faults": []}
        else:
            active: List[Dict[str, Any]] = [
                entry for entry in addr.fault_mapper
                if value & (1 << entry["charger_fault_code"])
            ]
            message = "; ".join(e["fault_message"] for e in active) or "No errors"
            result = {"code": value, "message": message, "active_faults": active}

        with self._data_lock:
            self.fault_status = result
        return result

    def read_system_status(self) -> Dict[str, Any]:
        addr = self.chargerAddress
        raw = self.comm.read_command(addr.SYSTEM_STATUS, addr.size[addr.SYSTEM_STATUS])
        value = self._raw_to_int(raw)

        if value is None:
            result = {"code": None, "message": "No response", "active_flags": []}
        else:
            active = [
                entry for entry in addr.system_status_mapper
                if value & (1 << entry["charger_fault_code"])
            ]
            message = "; ".join(e["fault_message"] for e in active) or \
                "System is operating normally"
            result = {"code": value, "message": message, "active_flags": active}

        with self._data_lock:
            self.system_status = result
        return result

    def read_charger_status(self) -> Dict[str, Any]:
        addr = self.chargerAddress
        raw = self.comm.read_command(addr.CHG_STATUS, addr.size[addr.CHG_STATUS])

        if raw is None or len(raw) < 2:
            result = {"code": None, "message": "No response", "active_flags": []}
        else:
            value = self._raw_to_int(raw)
            low_byte, high_byte = raw[0], raw[1]

            active = [
                entry for entry in addr.chg_status_mapper
                if (entry["byte"] == "low" and low_byte & (1 << entry["charger_fault_code"]))
                or (entry["byte"] == "high" and high_byte & (1 << entry["charger_fault_code"]))
            ]
            message = "; ".join(e["fault_message"] for e in active) or \
                "Charger is operating normally"
            result = {"code": value, "message": message, "active_flags": active}

        with self._data_lock:
            self.charger_status = result
        return result

    def read_data(self) -> Dict[str, Any]:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

        try:
            # --- CAN interface health check first: no point issuing reads on a dead bus ---
            if not self.comm.interface_exists():
                self.success = False
                self.status = "CAN_INTERFACE_DOWN"
                self.charger_initialized = False
                print(f"CAN interface {self.channel} is down")
                return {
                    "pdu_chgr": {
                        "timestamp": timestamp,
                        "chgr_model_name": "",
                        "chgr_status": "inactive",
                        "chgr_can_params": [],
                        "chgr_response": [],
                        "chgr_error": {
                            "chgr_error_message": "CAN_INTERFACE_DOWN",
                            "chgr_error_code": "CAN001",
                        },
                    }
                }

            if not self.charger_initialized:
                if not self.start_device():
                    self.success = False
                    self.status = "DEVICE_NOT_RESPONDING"
                    print(f"Charger did not respond on {self.channel}")
                    return {
                        "pdu_chgr": {
                            "timestamp": timestamp,
                            "chgr_model_name": "",
                            "chgr_status": "inactive",
                            "chgr_can_params": [],
                            "chgr_response": [],
                            "chgr_error": {
                                "chgr_error_message": "DEVICE_NOT_RESPONDING",
                                "chgr_error_code": "CAN002",
                            },
                        }
                    }

            # --- live reads / decode (unchanged logic, same helper methods) ---
            operation = self.read_operation()
            op_data = self.read_operating_data()
            fault = self.read_fault_status()

            self.last_comm_timestamp = time.time()
            self.success = True
            self.status = "ok"

            # Only real hardware faults (FAULT_STATUS register) are surfaced here -
            # chg_status / system_status carry normal operating-mode flags, not faults.
            active_faults = fault.get("active_faults") or []

            pdu_chgr = {
                "timestamp": timestamp,
                "chgr_model_name": self.chgr_model_name or "",
                "chgr_vout_DC": f"{op_data.get('vout')}V" if op_data.get("vout") is not None else None,
                "chgr_iout": f"{op_data.get('iout')}A" if op_data.get("iout") is not None else None,
                "chgr_temp": f"{op_data.get('temperature')}\u00b0C" if op_data.get("temperature") is not None else None,
            }

            vin_value = op_data.get("vin")
            model_name = (self.chgr_model_name or "").upper()
            if vin_value not in (None, 0.0) and "1200-48" in model_name:
                pdu_chgr["chgr_vin_AC"] = f"{vin_value}V"

            if active_faults:
                pdu_chgr["chgr_response_code"] = [
                    {"charger_fault_code": f["charger_fault_code"], "fault_message": f["fault_message"]}
                    for f in active_faults
                ]
                pdu_chgr["chgr_error"] = {
                    "chgr_error_message": "; ".join(f["fault_message"] for f in active_faults),
                    "chgr_error_code": ", ".join(f["application_code"] for f in active_faults),
                }
            else:
                # no fault - chgr_response_code is omitted entirely, chgr_error stays empty
                pdu_chgr["chgr_error"] = {}

            return {"pdu_chgr": pdu_chgr}

        except CANCommError as exc:
            print("read_data failed - CAN comm error:", exc)
            self.success = False
            self.status = "CAN_INTERFACE_DOWN"
            self.charger_initialized = False  # force re-init on next call
            return {
                "pdu_chgr": {
                    "timestamp": timestamp,
                    "chgr_model_name": "",
                    "chgr_status": "inactive",
                    "chgr_can_params": [],
                    "chgr_response": [],
                    "chgr_error": {
                        "chgr_error_message": "CAN_INTERFACE_DOWN",
                        "chgr_error_code": "CAN001",
                    },
                }
            }

        except Exception as exc:
            print("read_data failed:", exc)
            self.success = False
            self.status = f"read_data error: {exc}"
            self.charger_initialized = False  # force re-init on next call
            return {
                "pdu_chgr": {
                    "timestamp": timestamp,
                    "chgr_model_name": "",
                    "chgr_status": "inactive",
                    "chgr_can_params": [],
                    "chgr_response": [],
                    "chgr_error": {
                        "chgr_error_message": "CAN_READ_FAILURE",
                        "chgr_error_code": "CAN003",
                    },
                }
            }