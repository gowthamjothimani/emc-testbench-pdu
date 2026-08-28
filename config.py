"""
Central hardware/config constants for the EMC PDU Testbench.

Keeping everything that is board-specific (addresses, bus numbers, the
EEPROM window, CAN interface name) in one place means the rest of the
codebase never hardcodes a magic number twice. Change values here, not
inside the driver modules.
"""

# ---------------- I2C ----------------
I2C_BUS = 2                     # BeagleBone Black i2c-2 (P9_19/P9_20), same bus used by ACU testbench
HDC302X_ADDR = 0x47             # Temp/Hum sensor - same part/address as ACU board
EEPROM_ADDR = 0x59              # 24xx-series EEPROM on the PDU board (ACU used 0x50 - PDU uses 0x59)

# 24xx-series EEPROM page size. 32 is a safe default for 24LC32/24LC64-class
# parts; if the PDU's EEPROM part number is smaller/larger, adjust this and
# EEPROM_WINDOW below to match the actual chip datasheet.
EEPROM_PAGE_SIZE = 32

# Byte window inside the EEPROM reserved for the combined device_info +
# log_report JSON blob written at QC time. ASSUMPTION: no write-protect
# GPIO is wired on the PDU board (unlike the ACU's P8_11 WP pin) - if the
# PDU EEPROM *does* have a WP pin, set EEPROM_WP_GPIO to that pin name and
# eeprom.py will drive it automatically.
EEPROM_WP_GPIO = None           # e.g. "P8_11" if wired; None = no WP control
EEPROM_WINDOW_START = 0x0000
EEPROM_WINDOW_END = 0x0800      # 2KB window - adjust to match chip capacity

# ---------------- CAN ----------------
CAN_CHANNEL = "can1"            # SocketCAN interface used by charger + battery (matches PDU firmware)
CAN_BITRATE = 250000

# ---------------- MQTT ----------------
MQTT_DEFAULT_CONFIG = {
    "hostname": "10.30.250.241",
    "port": 1883,
    "topic": "emc_pdu_test",
    "username": "",
    "password": "",
}
MQTT_PING_TIMEOUT_S = 1.5       # reachability ping used for the status-bar network indicator

# ---------------- Driver mock mode ----------------
# When the real charger_address.py / can_communication.py / NPB1200_Charger.py
# and qhb.py driver files (already built for the PDU firmware stack) are not
# importable - e.g. developing the UI on a laptop with no CAN hardware - the
# interfaces below fall back to a simulated data source so the rest of the
# testbench (UI, logging, QC, EEPROM) can still be exercised end-to-end.
# Set FORCE_MOCK = True to force simulation even if the real drivers ARE
# importable (useful for a bench demo).
FORCE_MOCK = False
