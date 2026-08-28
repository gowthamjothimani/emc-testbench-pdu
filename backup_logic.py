"""
AC/Charger -> Battery backup truth table, per spec:

    AC input / Charger | Battery State | Charger connected | Status
    --------------------+---------------+--------------------+---------------------------
    ON                  | Ready         | Connected          | Running on AC/Charger
    ON                  | Charging      | Connected          | Running on AC
    OFF                 | Discharging   | Disconnected       | Running on Battery

Only the OFF / Discharging / Disconnected row is a *pass* for the backup
test itself - the other two rows describe normal AC-powered operation
and are shown for context/telemetry, not scored.
"""
import time

_BATTERY_STATE_NORMALIZED = {
    "ready": "Ready",
    "charging": "Charging",
    "discharging": "Discharging",
}


def classify_power_state(ac_charger_on: bool, battery_state: str, charger_connected: bool) -> str:
    """Maps live battery telemetry onto the truth table's Status column."""
    state = _BATTERY_STATE_NORMALIZED.get((battery_state or "").strip().lower(), battery_state)

    if ac_charger_on and state == "Ready" and charger_connected:
        return "Running on AC/Charger"
    if ac_charger_on and state == "Charging" and charger_connected:
        return "Running on AC"
    if (not ac_charger_on) and state == "Discharging" and (not charger_connected):
        return "Running on Battery"
    return "Unknown state combination"


def poll_for_discharge(battery_interface, timeout_s: float = 20.0, interval_s: float = 1.0) -> dict:
    """
    Call once the operator confirms AC/charger has been switched off.
    Polls the battery interface until battery_state == Discharging AND
    charger_connected == False, or the timeout elapses.

    Returns a result dict suitable for logging directly:
        {
            "requested": True,
            "confirmed_off_by_operator": True,
            "result": "pass" | "timeout",
            "observed_battery_state": "...",
            "observed_charger_connected": bool,
            "elapsed_s": float,
            "timestamp": "..."
        }
    """
    start = time.monotonic()
    observed_state = None
    observed_connected = None

    while (time.monotonic() - start) < timeout_s:
        data = battery_interface.read_data()
        basic = (data or {}).get("batt_basic", {})
        observed_state = basic.get("battery_state")
        observed_connected = basic.get("charger_connected")

        normalized = _BATTERY_STATE_NORMALIZED.get((observed_state or "").strip().lower(), observed_state)
        if normalized == "Discharging" and observed_connected is False:
            return {
                "requested": True,
                "confirmed_off_by_operator": True,
                "result": "pass",
                "observed_battery_state": observed_state,
                "observed_charger_connected": observed_connected,
                "elapsed_s": round(time.monotonic() - start, 1),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        time.sleep(interval_s)

    return {
        "requested": True,
        "confirmed_off_by_operator": True,
        "result": "timeout",
        "observed_battery_state": observed_state,
        "observed_charger_connected": observed_connected,
        "elapsed_s": round(timeout_s, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
