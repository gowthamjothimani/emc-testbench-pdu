import re
import subprocess
from config import CAN_CHANNEL

def get_can_status(channel: str = CAN_CHANNEL) -> dict:

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

        if "LOWER_UP" in text or re.search(r"state\s+UP", text):
            result["state"] = "UP"
        else:
            result["state"] = "DOWN"

        # CAN bus-error state 
        detail_match = re.search(r"can state (\S+)", text)
        can_state = detail_match.group(1).upper() if detail_match else None
        if can_state:
            result["detail"] = can_state
            result["health"] = "OK" if can_state == "ERROR-ACTIVE" else "ERROR"
        else:
            result["detail"] = "ERROR-ACTIVE (assumed)" if result["state"] == "UP" else "link down"
            result["health"] = "OK" if result["state"] == "UP" else "ERROR"

        # RX/TX error counters
        rx_match = re.search(r"re-started bus-errors\s+arbitration-lost\s+error-warning\s+error-passive\s+bus-off\n\s*(\d+)\s+(\d+)", text)
        # Fallback:
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
