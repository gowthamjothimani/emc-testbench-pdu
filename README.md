# EMC PDU Testbench

Flask + SocketIO test console for the PDU board, built alongside the same
UI theme/pattern as the EMC ACU Testbench reference app, targeting a
BeagleBone Black.

## Layout

```
app.py                 Flask + SocketIO app, routes, background threads
config.py              All board-specific constants (i2c bus/addrs, CAN
                        channel, EEPROM window, MQTT defaults, mock toggle)
eeprom.py               24xx-series EEPROM @ 0x59 on i2c-2 (adapted from
                        ACU's eeprom.py: different address, WP GPIO optional)
hdc302x.py / sensor_reader.py   Temp/Hum - reused verbatim from ACU
can_monitor.py           CAN1 uplink status (link state + bus health)
mqtt_client.py            MQTT publish/config, + broker ping for status bar
log_exporter.py            In-memory test session log -> JSON (PDU schema)
charger_interface.py        Adapter around the EXISTING NPB-1200 CAN driver
battery_interface.py         Adapter around the EXISTING QHB battery CAN driver
backup_logic.py               AC/Battery truth-table + guided backup test
templates/tester_info.html      Landing page (operator/model/project/serial)
templates/index.html             Test console: title bar / status bar / nav
                                  bar / 4 tabs (Inspection, Charger, Battery, DC Out)
static/styles.css, static/script.js, static/logo.png
```

## Plugging in the real charger & battery drivers

Per the PDU firmware project, the CAN driver stack for the Mean Well
NPB-1200 charger and QHB battery pack already exists and should **not**
be reimplemented here:

- `charger_address.py` - pure addressing data
- `can_communication.py` - SocketCAN I/O, retry logic, Notifier thread
- `NPB1200_Charger.py` - charger decode/business logic, `read_data()`
- `qhb.py` - battery decode/business logic, `read_data()` returning
  `batt_basic` / `batt_advance`

Copy those four files into this project's root, next to `app.py`. Both
`charger_interface.py` and `battery_interface.py` try to import them on
startup; if the import succeeds, the interfaces drive real hardware. If
it fails (e.g. running the UI on a laptop with no CAN adapter), both
interfaces fall back to a built-in mock data source so the rest of the
testbench (UI, inspection log, QC report, EEPROM read/write, MQTT
export) can still be exercised end-to-end. Set `FORCE_MOCK = True` in
`config.py` to force simulation even with real drivers present (bench
demo mode).

`battery_interface.py`'s mock mode also exposes a `set_mock_ac_present()`
hook, surfaced in the DC Out tab as "Simulate AC OFF / ON" so the battery
backup test can be walked through without real hardware. It's hidden
automatically once real hardware is detected (`GET /system/hw_status`).

## Assumptions worth checking against the actual PDU schematic

- **EEPROM**: 0x59 on i2c-2, no write-protect GPIO wired (unlike the ACU's
  P8_11). If the PDU EEPROM *does* have a WP pin, set `EEPROM_WP_GPIO` in
  `config.py` and `eeprom.py` will drive it automatically. The EEPROM
  page size (32B) and write window (0x0000-0x0800) are placeholders -
  adjust to the real chip's page size/capacity.
- **CAN**: `can1` @ 250 kbps, matching the existing PDU firmware
  configuration. `can_monitor.py` reads link state and bus-error state
  via `ip -details -statistics link show can1` (read-only netlink query -
  doesn't compete with the charger/battery drivers for the CAN socket).
- **Battery backup test**: polls for up to 20s after the operator
  confirms AC/charger is off, looking for `battery_state == "Discharging"`
  AND `charger_connected == False` in `batt_basic`. Adjust the timeout in
  `backup_logic.poll_for_discharge()` if the board's capacitor/relay
  transition takes longer to settle.
- **Temp/Hum**: reused as-is from the ACU testbench (same HDC302x part,
  same i2c-2 bus, address 0x47) - assumed identical sensor placement on
  the PDU board.

## Running

```
pip install -r requirements.txt
python app.py
```

Then browse to the BeagleBone's IP - you'll land on the tester info page
first; submitting it takes you to the test console and starts the
background status/charger/battery polling threads.
