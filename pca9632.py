import smbus2
import time

_MODE1  = 0x00
_MODE2  = 0x01
_PWM0   = 0x04  # RED
_PWM1   = 0x05  # GREEN
_PWM2   = 0x03  # BLUE
_PWM3   = 0x06  # WHITE (if present)
_LEDOUT = 0x08


class PCA9632:
    def __init__(self, i2c_bus: int = 2, address: int = 0x62):
        self.i2c_bus = i2c_bus
        self.address = address
        self.available = False
        self.bus = None

        self._attempt_init()

    def _attempt_init(self) -> bool:
        try:
            self.bus = smbus2.SMBus(self.i2c_bus)
            self._init_device()
            self.available = True
            return True
        except (OSError, IOError) as exc:
            print(f"PCA9632 not available, continuing without RGB device: {exc}")
            self.available = False
            self.bus = None
            return False

    def _ensure_initialized(self) -> bool:
        if self.available and self.bus is not None:
            return True

        return self._attempt_init()

    def _write(self, reg: int, val: int) -> None:
        if not self._ensure_initialized():
            return
        self.bus.write_byte_data(self.address, reg, val)

    def _init_device(self) -> None:
        if self.bus is None:
            self.bus = smbus2.SMBus(self.i2c_bus)

        self.bus.write_byte_data(self.address, _MODE1, 0x00)
        time.sleep(0.01)
        self.bus.write_byte_data(self.address, _MODE2, 0x00)
        self.bus.write_byte_data(self.address, _LEDOUT, 0xAA)

    def _set_channels(self, r: int, g: int, b: int, w: int = 0x00) -> None:
        self._write(_PWM0, r)
        self._write(_PWM1, g)
        self._write(_PWM2, b)
        self._write(_PWM3, w)


    def red(self, brightness: int = 0xFF) -> None:
        self._set_channels(r=brightness, g=0x00, b=0x00)
    def green(self, brightness: int = 0xFF) -> None:
        self._set_channels(r=0x00, g=brightness, b=0x00)

    def blue(self, brightness: int = 0xFF) -> None:
        self._set_channels(r=0x00, g=0x00, b=brightness)

    def white(self, brightness: int = 0xFF) -> None:
        self._set_channels(r=brightness, g=brightness, b=brightness)

    def custom(self, r: int, g: int, b: int, w: int = 0x00) -> None:
        self._set_channels(r=r, g=g, b=b, w=w)

    def off(self) -> None:
        self._set_channels(r=0x00, g=0x00, b=0x00, w=0x00)

    def close(self) -> None:
        self.off()
        if self.bus is not None:
            self.bus.close()
            self.bus = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()