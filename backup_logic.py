import time

BATTERY_BACKUP_STATES = ("Ready", "Discharging")


def classify_power_state(ac_charger_on: bool, batt_state: str, batt_charger: str) -> str:
    state = (batt_state or "").strip()
    charger = (batt_charger or "").strip().lower()

    if ac_charger_on and state == "Ready" and charger == "connected":
        return "Running on AC/Charger"
    if ac_charger_on and state == "Charging" and charger == "connected":
        return "Running on AC"
    if (not ac_charger_on) and state in BATTERY_BACKUP_STATES and charger == "disconnected":
        return "Running on Battery"
    return "Unknown state combination"


def poll_for_discharge(battery_interface, timeout_s: float = 20.0, interval_s: float = 1.0) -> dict:
    start = time.monotonic()
    observed_state = None
    observed_charger = None
    # Once the charger reports "disconnected" during this poll, latch it -
    # CAN/relay noise can flicker it back to "connected" for a beat while
    # the backup test is actually running, which shouldn't undo a real
    # disconnect that already happened.
    charger_disconnected_locked = False

    while (time.monotonic() - start) < timeout_s:
        data = battery_interface.read_data()
        batt = (data or {}).get("pdu_batt", {})

        if batt.get("batt_error") or not batt.get("batt_basic"):
            return {
                "requested": True,
                "confirmed_off_by_operator": True,
                "result": "na",
                "observed_battery_state": None,
                "observed_charger_connected": None,
                "elapsed_s": round(time.monotonic() - start, 1),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        basic = batt.get("batt_basic", {})
        observed_state = basic.get("batt_state")
        observed_charger = basic.get("batt_charger")

        if (observed_charger or "").strip().lower() == "disconnected":
            charger_disconnected_locked = True

        if (observed_state or "").strip() in BATTERY_BACKUP_STATES and charger_disconnected_locked:
            return {
                "requested": True,
                "confirmed_off_by_operator": True,
                "result": "pass",
                "observed_battery_state": observed_state,
                "observed_charger_connected": "disconnected",
                "elapsed_s": round(time.monotonic() - start, 1),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        time.sleep(interval_s)

    return {
        "requested": True,
        "confirmed_off_by_operator": True,
        "result": "timeout",
        "observed_battery_state": observed_state,
        "observed_charger_connected": "disconnected" if charger_disconnected_locked else observed_charger,
        "elapsed_s": round(timeout_s, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
