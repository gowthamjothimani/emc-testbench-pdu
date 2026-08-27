import datetime
import json
import os
import threading
import struct
import time

try:
    import can
except Exception:  # pragma: no cover - runtime on non-CAN hosts
    can = None

from .qhb_address import QHB_ADDRESS_MAP

class CAN_QHB:

    def __init__(self):
        self.addr = QHB_ADDRESS_MAP()
        self.channel = "can1"
        self.bus = None
        self.success = False
        self.status = "INIT"
        self.pack_voltage = 0.0
        self.pack_current = 0.0
        self.soc = 0
        self.max_charge_voltage = 0.0
        self.max_charge_current = 0.0
        self.max_discharge_voltage = 0.0
        self.max_discharge_current = 0.0
        self.max_temp = 0
        self.min_temp = 0
        self.active_battery = 0
        self.passive_battery = 0
        self.pack_state = "Unknown"
        self.smart_charger = False
        self.nodes = {}
        self.last_updated = None
        self.bus_lock = threading.Lock()
        self.sdo_timeout = 2
        self.sdo_results = {}
        self.sdo_objects = [
            ("Vendor ID", self.addr.VENDOR_ID),
            ("Product Code", self.addr.PRODUCT_ID),
            ("Revision", self.addr.REVISION_NUMBER),
            ("Serial Number", self.addr.SERIAL_NUMBER),
            ("Battery Capacity", self.addr.BATTERY_CAPACITY),
            ("Battery SOH", self.addr.BATTERY_SOH),
            ("Cycles", self.addr.CYCLE_COUNT),
            ("Deep Discharges", self.addr.DEEP_DISCHARGE),
            ("Sub-zero Charges", self.addr.SUB_ZERO_CHARGERS),
            ("Maximum Voltage", self.addr.MAX_VOLTAGE),
            ("Humidity", self.addr.HUMIDITY_LEVEL),
            ("Maximum Charge", self.addr.MAX_CHARGE),
            ("Maximum Discharge", self.addr.MAX_DISCHARGE),
            ("Minimum Voltage", self.addr.MIN_VOLTAGE),
            ("Maximum Temperature Sensor 1", self.addr.MAX_TEMP_SENSOR_1),
            ("Maximum Temperature Sensor 2", self.addr.MAX_TEMP_SENSOR_2),
            ("Bash Counter", self.addr.BASH_COUNTER),
            ("Wh Used Since Last Charge", self.addr.POWER_USED_SINCE_LAST_CHARGE),
        ]
        self.vendor_id = None
        self.product_code = None
        self.revision = None
        self.serial_number = None
        self.battery_capacity_full = None
        self.battery_capacity_remaining = None
        self.soh = None
        self.cycles = None
        self.deep_discharges = None
        self.sub_zero_charges = None
        self.max_voltage = None
        self.min_voltage = None
        self.humidity = None
        self.max_charge = None
        self.max_discharge = None
        self.max_temp_sensor_1 = None
        self.max_temp_sensor_2 = None
        self.bash_counter = None
        self.wh_used_since_last_charge = None
        self.batt_capacity_full_ah = None
        self.batt_capacity_remaining_ah = None
        self.batt_humidity = None
        self.batt_max_temp_sensor_1 = None
        self.batt_max_temp_sensor_2 = None
        self.batt_bash_counter = None
        self.batt_wh_used_since_last_charge = None
        self.sdo_initialized = False

    #  INIT DEVICE 
    def init_device(self):
        try:
            if can is None:
                raise ModuleNotFoundError("python-can is not installed")

            bus_factory = getattr(can, "Bus", None)
            if bus_factory is None:
                interface_mod = getattr(can, "interface", None)
                if interface_mod is not None:
                    bus_factory = getattr(interface_mod, "Bus", None)
            if bus_factory is None:
                bus_mod = getattr(can, "bus", None)
                if bus_mod is not None:
                    bus_factory = getattr(bus_mod, "Bus", None)
            if bus_factory is None:
                raise AttributeError("python-can installation does not expose a Bus factory")

            self.bus = bus_factory(
                channel=self.channel,
                interface="socketcan"
            )
            self.success = True
            self.status = "CAN1_INITIALIZED"
            print("[CAN] CAN1 initialized successfully")
            return True
        except Exception as e:
            self.success = False
            self.status = "CAN1_INIT_FAILED"
            print(f"[ERROR] CAN1 initialization failed: {e}")
            self.bus = None
            return False

    #  CAN LINK HEALTH CHECK 
    def _interface_exists(self):
        """
        Lightweight SocketCAN link presence check (no bus I/O).
        Lets read_data() fail fast with CAN_INTERFACE_DOWN before
        touching self.bus, instead of blocking on a dead interface.
        """
        return os.path.isdir(f"/sys/class/net/{self.channel}")

    #  LISTEN 
    def start_device(self):
        if not self.bus:
            print("[ERROR] CAN bus not initialized")
            return False
        print("[CAN] Listening on CAN1 ...")

        while True:
            with self.bus_lock:
                msg = self.bus.recv(timeout=1.0)
            if msg is None:
                continue

            self.last_updated = datetime.datetime.utcnow()

            # PACK DATA 1
            if msg.arbitration_id == self.addr.PACK_DATA_1:
                self.read_pack_data_1(msg.data)

            # PACK DATA 2
            elif msg.arbitration_id == self.addr.PACK_DATA_2:
                self.read_pack_data_2(msg.data)

            # MAXIMUM ALLOWED PACK VALUES   
            elif msg.arbitration_id == self.addr.MAXIMUM_ALLOWED_VALUES:
                self.read_pack_data_3(msg.data)
            
            elif msg.arbitration_id >= self.addr.INDIVIDUAL_DATA_BASE:
                self.read_individual_battery(msg.data)

        return True
            

    #  DECODE 
    def read_pack_data_1(self, data):
        if len(data) < 8:
            return

        self.soc = data[self.addr.PD1_SOC]
        voltage_raw = (data[self.addr.PD1_VOLTAGE_MSB] << 8) | data[self.addr.PD1_VOLTAGE_LSB]
        self.pack_voltage = round(voltage_raw / 1024.0, 2)
        self.active_battery = data[self.addr.PD1_ACTIVE_BAT]
        self.passive_battery = data[self.addr.PD1_PASSIVE_BAT]
        self.pack_state = "Unknown"
        self.success = True
        self.status = "PACK_DATA_1_RECEIVED"

        # print("\n=== PACK DATA 1 (0x18F) ===")
        # print(f"SoC        : {self.soc}{self.addr.UNIT_PERCENT}")
        # print(f"Voltage    : {self.pack_voltage:.2f}{self.addr.UNIT_VOLT}")
        # print(f"Active Bat : {self.active_battery}")
        # print(f"Passive Bat: {self.passive_battery}")

    #  DECODE 0x28F 
    def read_pack_data_2(self, data):
        try:
            if len(data) < 8:
                return
            # Pack state
            pack_state = data[self.addr.PD2_PACK_STATE]
            self.pack_state = self.addr.BATTERY_STATE.get(pack_state, "Unknown")

            curr_raw = (
                (data[self.addr.PD2_CURRENT_MSB] << 8) |
                data[self.addr.PD2_CURRENT_LSB]
            )
            #print(f"Raw Current: {curr_raw}")
            if curr_raw & 0x8000:
                curr_raw = curr_raw - 0x10000
            
            self.pack_current = round(curr_raw)
            self.max_temp = data[self.addr.PD2_MAX_TEMP] - self.addr.TEMP_OFFSET
            self.min_temp = data[self.addr.PD2_MIN_TEMP] - self.addr.TEMP_OFFSET
            self.smart_charger = data[self.addr.PD2_SMART_CHARGER] == 1
            #print(self.smart_charger)
            self.success = True
            self.status = "PACK_DATA_2_RECEIVED"

            # print("\n=== PACK DATA 2 (0x28F) ===")
            # print(f"State      : {self.pack_state}")
            # print(f"Current    : {self.pack_current:.1f}{self.addr.UNIT_CURRENT}")
            # print(f"Max Temp   : {self.max_temp}{self.addr.UNIT_TEMP}")
            # print(f"Min Temp   : {self.min_temp}{self.addr.UNIT_TEMP}")
            # print(f"Charger Status: {'Connected' if self.smart_charger else 'Not Connected'}")
   
        except Exception as e:
            print(f"[ERROR] PD2 decode failure: {e}")


    def read_pack_data_3(self, data):
        try:
            if len(data) < 8:
                return

            self.max_charge_voltage = round(((data[1] << 8) | data[0]) / 10.0, 1)
            self.max_charge_current = round(((data[3] << 8) | data[2]) / 10.0, 1)
            self.max_discharge_current = round(((data[5] << 8) | data[4]) / 10.0, 1)
            self.max_discharge_voltage = round(((data[7] << 8) | data[6]) / 10.0, 1)
            self.success = True
            self.status = "PACK_LIMITS_RECEIVED"

            # print("\n=== PACK LIMITS (0x351) ===")
            # print(f"Max Charge Voltage   : {self.max_charge_voltage:.1f}{self.addr.UNIT_VOLT}")
            # print(f"Max Charge Current   : {self.max_charge_current:.1f}{self.addr.UNIT_CURRENT}")
            # print(f"Max Discharge Current: {self.max_discharge_current:.1f}{self.addr.UNIT_CURRENT}")
            # print(f"Max Discharge Volt   : {self.max_discharge_voltage:.1f}{self.addr.UNIT_VOLT}")

        except Exception as e:
            print(f"[ERROR] 0x351 decode failure: {e}")
    
    def read_individual_battery(self, data):
        try:
            if len(data) < 8:
                return
            node_id = len(self.nodes) + 1
            node_name = f"Cell_{node_id}"
            soc = data[self.addr.IND_SOC]
            state = self.addr.BATTERY_STATE.get(
                data[self.addr.IND_STATE_OF_BATTERY],
                "Unknown"
            )
            raw_current = data[self.addr.IND_CURRENT]
            if raw_current & 0x80:
                raw_current = raw_current - 0x100

            self.nodes[node_name] = {
                "permission": data[self.addr.IND_PERMISSION],
                "heating_mode": data[self.addr.IND_HEATING_MODE],
                "virtual_pack": data[self.addr.IND_VIRTUAL_ID_PACK],
                "virtual_cell": data[self.addr.IND_VIRTUAL_ID_CELL],
                "soc": {
                    "value": soc,
                    "unit": self.addr.UNIT_PERCENT,
                },
                "state": state,
                "current": {
                    "value": round(raw_current / 10.0, 1),
                    "unit": self.addr.UNIT_CURRENT,
                },
                "temperature": {
                    "value": data[self.addr.IND_TEMP] - self.addr.TEMP_OFFSET,
                    "unit": self.addr.UNIT_TEMP,
                },
            }
            self.success = True
            self.status = "INDIVIDUAL_BATTERY_RECEIVED"

        except Exception as e:
            print(f"[ERROR] 0x48F decode failure: {e}")

    def read_data(self):
        currentTime = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

        try:
            # --- CAN link health check first: no point issuing SDO reads on a dead bus ---
            if not self._interface_exists():
                self.success = False
                self.status = "CAN_INTERFACE_DOWN"
                batt_error = {
                    "success": False,
                    "status": "CAN_INTERFACE_DOWN",
                    "device_type": "QHB_BATTERY",
                    "error_code": "CAN001",
                    "error_message": f"CAN interface {self.channel} is down",
                    "timestamp": currentTime,
                }
                print(batt_error["error_message"])
                return {
                    "pdu_batt": {
                        "batt_name": "PDU Battery",
                        "batt_type": "1",
                        "batt_serialNumber": self.serial_number or "",
                        "batt_firmwareVersion": self.revision or "",
                        "batt_capacity": self.batt_capacity_full_ah,
                        "batt_status": "inactive",
                        "batt_basic": {},
                        "batt_advance": {},
                        "batt_error": batt_error,
                    }
                }

            if self.bus is None:
                self.success = False
                self.status = "CAN_BUS_NOT_INITIALIZED"
                batt_error = {
                    "success": False,
                    "status": "CAN_BUS_NOT_INITIALIZED",
                    "device_type": "QHB_BATTERY",
                    "error_code": "CAN002",
                    "error_message": "CAN bus handle not initialized - call init_device() first",
                    "timestamp": currentTime,
                }
                print(batt_error["error_message"])
                return {
                    "pdu_batt": {
                        "batt_name": "PDU Battery",
                        "batt_type": "1",
                        "batt_serialNumber": self.serial_number or "",
                        "batt_firmwareVersion": self.revision or "",
                        "batt_capacity": self.batt_capacity_full_ah,
                        "batt_status": "inactive",
                        "batt_basic": {},
                        "batt_advance": {},
                        "batt_error": batt_error,
                    }
                }

            # --- SDO reads / PDO decode (helper methods) ---
            if not self.sdo_initialized:
                self.update_sdo_values()

            self.success = True
            self.status = "ok"

            batt_basic = {
                "batt_state": self.pack_state,
                "batt_charger": "connected" if self.smart_charger else "disconnected",
                "batt_soc": f"{self.soc}%",
                "batt_voltage": f"{self.pack_voltage:.2f}V",
                "batt_current": f"{self.pack_current:.1f}A",
                "batt_active_pack": self.active_battery,
                "batt_temp_max": f"{self.max_temp}°C",
                "batt_temp_min": f"{self.min_temp}°C",
            }

            batt_advance = {
                "batt_error_code": "0",
                "batt_error_message": "No errors",
                "batt_health": {
                    "batt_deep_discharge": self.deep_discharges if self.deep_discharges is not None else "UNKNOWN",
                    "batt_subzero": self.sub_zero_charges if self.sub_zero_charges is not None else "UNKNOWN",
                    "batt_cycle_life": self.cycles if self.cycles is not None else "UNKNOWN",
                    "batt_max_volt": f"{self.max_charge_voltage:.1f}V",
                    "batt_min_volt": f"{self.max_discharge_voltage:.1f}V",
                    "batt_max_chrg_curr": f"{self.max_charge_current:.1f}A",
                    "batt_max_dischrg_curr": f"{self.max_discharge_current:.1f}A",
                    "batt_capacity_full_ah": self.batt_capacity_full_ah,
                    "batt_capacity_remaining_ah": self.batt_capacity_remaining_ah,
                    "batt_humidity": self.batt_humidity,
                    "batt_max_temp_sensor_1": self.batt_max_temp_sensor_1,
                    "batt_max_temp_sensor_2": self.batt_max_temp_sensor_2,
                    "batt_bash_counter": self.batt_bash_counter,
                    "batt_wh_used_since_last_charge": self.batt_wh_used_since_last_charge,
                },
            }

            return {
                "pdu_batt": {
                    "timestamp": currentTime,
                    "batt_name": "PDU Battery",
                    "batt_type": "1",
                    "batt_serialNumber": self.serial_number or "",
                    "batt_firmwareVersion": self.revision or "",
                    "batt_status": "active" if self.pack_state not in (None, "", "Unknown") else "inactive",
                    "batt_basic": batt_basic,
                    "batt_advance": batt_advance,
                    "batt_error": {},
                }
            }

        except can.CanError as exc:
            print(f"[ERROR] read_data CAN bus error: {exc}")
            self.success = False
            self.status = "CAN_INTERFACE_DOWN"
            batt_error = {
                "success": False,
                "status": "CAN_INTERFACE_DOWN",
                "device_type": "QHB_BATTERY",
                "error_code": "CAN001",
                "error_message": "CAN_INTERFACE_DOWN",
                "timestamp": currentTime,
            }
            return {
                "pdu_batt": {
                    "batt_name": "PDU Battery",
                    "batt_type": "1",
                    "batt_serialNumber": self.serial_number or "",
                    "batt_firmwareVersion": self.revision or "",
                    "batt_capacity": self.batt_capacity_full_ah,
                    "batt_status": "inactive",
                    "batt_basic": {},
                    "batt_advance": {},
                    "batt_error": batt_error,
                }
            }

        except Exception as exc:
            print(f"[ERROR] read_data failed: {exc}")
            self.success = False
            self.status = f"read_data error: {exc}"
            batt_error = {
                "success": False,
                "status": "CAN_READ_FAILURE",
                "device_type": "QHB_BATTERY",
                "error_code": "CAN003",
                "error_message": "CAN_READ_FAILURE",
                "timestamp": currentTime,
            }
            return {
                "pdu_batt": {
                    "batt_name": "PDU Battery",
                    "batt_type": "1",
                    "batt_serialNumber": self.serial_number or "",
                    "batt_firmwareVersion": self.revision or "",
                    "batt_capacity": self.batt_capacity_full_ah,
                    "batt_status": "inactive",
                    "batt_basic": {},
                    "batt_advance": {},
                    "batt_error": batt_error,
                }
            }

    def read_sdo(self, index_low, index_high, subindex):
        if self.bus is None:
            return None

        request = can.Message(
            arbitration_id=self.addr.SDO_REQUEST_ID,
            is_extended_id=False,
            data=[
                0x40,
                index_low,
                index_high,
                subindex,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )

        with self.bus_lock:
            self.bus.send(request)
            deadline = time.time() + self.sdo_timeout

            while time.time() < deadline:
                response = self.bus.recv(timeout=0.2)
                if response is None:
                    continue
                if response.arbitration_id != self.addr.SDO_RESPONSE_ID:
                    continue
                #print(f"[SDO] response for {index_low:02X}:{index_high:02X}:{subindex} -> {response.data.hex()}")
                return response.data

        #print(f"[SDO] timeout for {index_low:02X}:{index_high:02X}:{subindex}")
        return None

    def decode_sdo_response(self, name, response):
        if response is None or len(response) < 8:
            return None

        if name == "Battery Capacity":
            full = self.u16(response[4], response[5])
            remain = self.u16(response[6], response[7])
            return {"full_ah": full, "remaining_ah": remain}

        value = self.u32(response[4:8])

        if name in ("Maximum Voltage", "Minimum Voltage"):
            return round(value / 10.0, 1)

        return value

    def update_sdo_values(self):
        found_any = False
        for name, index_tuple in self.sdo_objects:
            response = self.read_sdo(*index_tuple)
            parsed = self.decode_sdo_response(name, response)
            self.sdo_results[name] = parsed
            #print(f"[SDO] {name}: {parsed}")

            if parsed is not None:
                found_any = True

            if name == "Vendor ID":
                self.vendor_id = parsed
            elif name == "Product Code":
                self.product_code = parsed
            elif name == "Revision":
                self.revision = parsed
            elif name == "Serial Number":
                self.serial_number = parsed
            elif name == "Battery Capacity" and isinstance(parsed, dict):
                self.battery_capacity_full = parsed.get("full_ah")
                self.battery_capacity_remaining = parsed.get("remaining_ah")
                self.batt_capacity_full_ah = parsed.get("full_ah")
                self.batt_capacity_remaining_ah = parsed.get("remaining_ah")
            elif name == "Battery SOH":
                self.soh = parsed
            elif name == "Cycles":
                self.cycles = parsed
            elif name == "Deep Discharges":
                self.deep_discharges = parsed
            elif name == "Sub-zero Charges":
                self.sub_zero_charges = parsed
            elif name == "Maximum Voltage":
                self.max_voltage = parsed
            elif name == "Minimum Voltage":
                self.min_voltage = parsed
            elif name == "Humidity":
                self.humidity = parsed
                self.batt_humidity = parsed
            elif name == "Maximum Charge":
                self.max_charge = parsed
            elif name == "Maximum Discharge":
                self.max_discharge = parsed
            elif name == "Maximum Temperature Sensor 1":
                self.max_temp_sensor_1 = parsed
                self.batt_max_temp_sensor_1 = parsed
            elif name == "Maximum Temperature Sensor 2":
                self.max_temp_sensor_2 = parsed
                self.batt_max_temp_sensor_2 = parsed
            elif name == "Bash Counter":
                self.bash_counter = parsed
                self.batt_bash_counter = parsed
            elif name == "Wh Used Since Last Charge":
                self.wh_used_since_last_charge = parsed
                self.batt_wh_used_since_last_charge = parsed

        self.status = "SDO_VALUES_RECEIVED"
        self.success = self.success or any(value is not None for value in self.sdo_results.values())

    def u16(self, lo, hi):
        return (hi << 8) | lo

    def u32(self, data):
        return struct.unpack("<I", bytes(data))[0]