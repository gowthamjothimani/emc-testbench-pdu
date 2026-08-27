import time

try:
    import smbus2
except Exception:  # pragma: no cover - runtime on non-BBB hosts
    smbus2 = None

try:
    import Adafruit_BBIO.GPIO as GPIO
except Exception:  # pragma: no cover - runtime on non-BBB hosts
    GPIO = None


class EEPROM:
    def __init__(self):
        self.eeprom_addr = 0x50
        self.wp_gpio = "P8_11"
        self.bus = None
        self.gpio_available = GPIO is not None and smbus2 is not None
        if self.gpio_available:
            self.bus = smbus2.SMBus(2)
            GPIO.setup(self.wp_gpio, GPIO.OUT)
            self.write_protect(False)

    def write_protect(self, enable_write):
        if not self.gpio_available:
            return
        GPIO.output(self.wp_gpio, GPIO.LOW if enable_write else GPIO.HIGH)

    def write_eeprom(self, start_addr, data):
        try:
            if not self.gpio_available or self.bus is None:
                return False
            self.write_protect(True)
            for offset, byte in enumerate(data):
                mem_addr = start_addr + offset
                addr_high = (mem_addr >> 8) & 0xFF
                addr_low = mem_addr & 0xFF
                write_msg = smbus2.i2c_msg.write(self.eeprom_addr, [addr_high, addr_low, byte])
                self.bus.i2c_rdwr(write_msg)
                time.sleep(0.01)
            self.write_protect(False)
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def read_eeprom(self, start_addr, length):
        try:
            if not self.gpio_available or self.bus is None:
                return []
            data_out = []
            for offset in range(length):
                mem_addr = start_addr + offset
                addr_high = (mem_addr >> 8) & 0xFF
                addr_low = mem_addr & 0xFF
                self.bus.i2c_rdwr(smbus2.i2c_msg.write(self.eeprom_addr, [addr_high, addr_low]))
                read_msg = smbus2.i2c_msg.read(self.eeprom_addr, 1)
                self.bus.i2c_rdwr(read_msg)
                data_out.append(list(read_msg)[0])
            return data_out
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    def close(self):
        if GPIO is not None:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
        self.bus = None
