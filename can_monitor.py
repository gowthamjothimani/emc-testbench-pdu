"""
CAN1 uplink status for the status bar.

Reports two things the operator needs at a glance:
  - link state:   UP / DOWN            (interface brought up, bitrate set)
  - health:       OK / ERROR           (bus-off or climbing error counters
                                         means frames aren't actually
                                         getting through even if link is UP)

Implemented via `ip -details -statistics link show <iface>` rather than a
raw SocketCAN bind, so it works even while the charger/battery drivers
already own the CAN socket - this is a read-only netlink query, not a
second bus participant.
"""
import re
import subprocess

from config import CAN_CHANNEL


def get_can_status(channel: str = CAN_CHANNEL) -> dict:
    """
    Returns:
        {
            "state": "UP" | "DOWN" | "UNKNOWN",
            "health": "OK" | "ERROR",
            "rx_errors": int,
            "tx_errors": int,
            "detail": str   # human-readable, e.g. "ERROR-ACTIVE" / "BUS-OFF"
        }
    """
    result = {
        "state": "UNKNOWN",
        "health": "ERROR",
        "rx_errors": 0,
        "tx_errors": 0,
        "detail": "no data",
    }

    try:
        out = subprocess.run(
            ["ip", "-details", "-statistics", "link", "show", channel],
            capture_output=True, text=True, timeout=2.0
        )
        text = out.stdout

        if not text:
            result["detail"] = out.stderr.strip() or "interface not found"
            return result

        # Link state: "<UP,LOWER_UP,ECHO>" or "state UP" / "state DOWN"
        if "LOWER_UP" in text or re.search(r"state\s+UP", text):
            result["state"] = "UP"
        else:
            result["state"] = "DOWN"

        # CAN bus-error state (only present with -details on a can iface)
        detail_match = re.search(r"can state (\S+)", text)
        can_state = detail_match.group(1).upper() if detail_match else None
        if can_state:
            result["detail"] = can_state
            result["health"] = "OK" if can_state == "ERROR-ACTIVE" else "ERROR"
        else:
            result["detail"] = "ERROR-ACTIVE (assumed)" if result["state"] == "UP" else "link down"
            result["health"] = "OK" if result["state"] == "UP" else "ERROR"

        # RX/TX error counters, if the kernel driver exposes them
        rx_match = re.search(r"re-started bus-errors\s+arbitration-lost\s+error-warning\s+error-passive\s+bus-off\n\s*(\d+)\s+(\d+)", text)
        # Fallback: generic byte/error counters from -s
        gen_match = re.search(r"RX:.*?\n\s*\d+\s+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+", text)
        if gen_match:
            result["rx_errors"] = int(gen_match.group(1))
        gen_tx_match = re.search(r"TX:.*?\n\s*\d+\s+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+", text)
        if gen_tx_match:
            result["tx_errors"] = int(gen_tx_match.group(1))

    except FileNotFoundError:
        result["detail"] = "'ip' command not found (not running on Linux/BeagleBone)"
    except subprocess.TimeoutExpired:
        result["detail"] = "ip command timed out"
    except Exception as e:
        result["detail"] = f"error: {e}"

    return result
