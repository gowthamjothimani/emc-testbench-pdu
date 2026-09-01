import time
from config import PUSHBUTTON_GPIO, PUSHBUTTON_REQUIRED_PRESSES
import Adafruit_BBIO.GPIO as GPIO

class PushbuttonMonitor:
    def __init__(self, pin: str = PUSHBUTTON_GPIO, required_presses: int = PUSHBUTTON_REQUIRED_PRESSES):
        self.pin = pin
        self.required_presses = required_presses
        self.press_count = 0
        self.working_recorded = False
        self._available = GPIO is not None

        if self._available:
            GPIO.setup(self.pin, GPIO.IN)
        else:
            print(f"PushbuttonMonitor: Adafruit_BBIO not available - "
                  f"pin {self.pin} can't be read on this machine, indicator will report NA.")

    def run_forever(self, on_update):
        if not self._available:
            on_update({"status": "na", "label": "NO GPIO", "color": "lightgray"})
            return

        last_pressed = False
        while True:
            pressed = not GPIO.input(self.pin)  # active-low, same convention as ACU

            if pressed and not last_pressed:
                self.press_count += 1
                if self.press_count >= self.required_presses:
                    self.working_recorded = True

            if pressed:
                status = "working" if self.working_recorded else "error"
                label = f"PRESSED ({self.press_count}/{self.required_presses})"
                color = "lightgreen" if self.working_recorded else "lightcoral"
            else:
                status = "working" if self.working_recorded else "error"
                label = "RELEASED"
                color = "lightgreen" if self.working_recorded else "lightcoral"

            on_update({"status": status, "label": label, "color": color})
            last_pressed = pressed
            time.sleep(0.2)
