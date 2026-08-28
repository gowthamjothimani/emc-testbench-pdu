"""
24xx-series EEPROM driver for the PDU board.

Adapted from the ACU testbench's eeprom.py:
  - address changed 0x50 -> 0x59 (per PDU board schematic)
  - write-protect GPIO is optional here (EEPROM_WP_GPIO in config.py);
    the ACU board hard-wires P8_11 for WP, the PDU may not
  - added probe() - a non-destructive presence check used by the
    status bar ("EEPROM: GOOD/ERROR" at 0x59 on i2c-2)
"""
import smbus2
import time

from config import I2C_BUS, EEPROM_ADDR, EEPROM_WP_GPIO

try:
    import Adafruit_BBIO.GPIO as GPIO
except ImportError:
    GPIO = None  # allows import on a non-BeagleBone dev machine


class EEPROM:
    def __init__(self):
        self.eeprom_addr = EEPROM_ADDR
        self.wp_gpio = EEPROM_WP_GPIO
        self.bus = smbus2.SMBus(I2C_BUS)

        if self.wp_gpio and GPIO:
            GPIO.setup(self.wp_gpio, GPIO.OUT)
            self.write_protect(False)

    def write_protect(self, enable_write):
        if not (self.wp_gpio and GPIO):
            return  # no WP line wired on this board - nothing to do
        GPIO.output(self.wp_gpio, GPIO.LOW if enable_write else GPIO.HIGH)

    def probe(self):
        """
        Non-destructive presence check for the status bar.
        Attempts a zero-length address-only write; an ACK means a device
        is present at EEPROM_ADDR on I2C_BUS. Returns True/False.
        """
        try:
            msg = smbus2.i2c_msg.write(self.eeprom_addr, [0x00, 0x00])
            self.bus.i2c_rdwr(msg)
            return True
        except Exception:
            return False

    def write_eeprom(self, start_addr, data):
        if any(byte == 0b10000000 for byte in data):
            raise ValueError(
                "Refusing to write 0b10000000 to EEPROM address 0x59: "
                "this command remotely shuts down the unit."
            )

        try:
            self.write_protect(True)
            for offset, byte in enumerate(data):
                mem_addr = start_addr + offset
                addr_high = (mem_addr >> 8) & 0xFF
                addr_low = mem_addr & 0xFF
                write_msg = smbus2.i2c_msg.write(self.eeprom_addr, [addr_high, addr_low, byte])
                self.bus.i2c_rdwr(write_msg)
                time.sleep(0.01)
            self.write_protect(False)
        except Exception as e:
            print(f"EEPROM write error: {e}")
            raise

    def read_eeprom(self, start_addr, length):
        try:
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
            print(f"EEPROM read error: {e}")
            raise

    def close(self):
        if GPIO:
            GPIO.cleanup()
        self.bus.close()
