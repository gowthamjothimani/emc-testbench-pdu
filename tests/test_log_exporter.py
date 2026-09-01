import sys
import types

from config import EEPROM_WINDOW_END
from log_exporter import LogExporter
from charger_interface import ChargerInterface
from Charger.can_communication import CANCommunication


class DummyMQTT:
    def publish_data(self, data):
        return None


def test_battery_status_latches_success_after_once_working():
    log = LogExporter(DummyMQTT())

    log.set_battery_status({"pdu_batt": {"batt_basic": {"batt_voltage": "52.10V"}}}, True, "Battery interface working")
    assert log.battery_status["locked_working"] is True

    log.set_battery_status({"pdu_batt": {"batt_error": {"error_code": "CAN001", "error_message": "disconnected"}}}, False, "CAN001: disconnected")
    assert log.battery_status["locked_working"] is True
    assert log.get_last_log()["battery-status"]["locked_working"] is True


def test_indicator_tracking_tracks_pushbutton_and_rgb():
    log = LogExporter(DummyMQTT())

    log.set_pushbutton_status("working")
    log.set_indicator("rgb_led", "working", "red")
    log.set_indicator("rgb_led", "working", "green")
    log.set_indicator("rgb_led", "working", "blue")

    current = log.get_last_log()
    assert current["indicator-status"]["pushbutton"] == "working"
    assert current["indicator-status"]["rgb_led"]["blue"] == "working"
    assert current["indicator-status"]["rgb_led_status"] == "working"


def test_charger_status_requires_real_telemetry():
    assert ChargerInterface.is_working({"pdu_chgr": {"chgr_error": {}}}) == (False, "No charger telemetry received")
    assert ChargerInterface.is_working({"pdu_chgr": {"chgr_vout_DC": "48.0V", "chgr_error": {}}}) == (True, "Charger interface working")


def test_charger_can_protocol_uses_register_read_request_and_node_write_id():
    class FakeMessage:
        def __init__(self, arbitration_id, data, is_extended_id=True):
            self.arbitration_id = arbitration_id
            self.data = list(data)
            self.is_extended_id = is_extended_id

    class FakeBus:
        def __init__(self):
            self.sent = []

        def send(self, msg):
            self.sent.append((msg.arbitration_id, list(msg.data)))

        def recv(self, timeout=None):
            return None

    fake_bus = FakeBus()
    fake_can = types.SimpleNamespace(Message=FakeMessage, Bus=lambda channel, interface: fake_bus)
    sys.modules["can"] = fake_can

    comm = CANCommunication(channel="can1", bitrate=250000, tx_id=0x000C0103, rx_id=0x000C0003)
    comm.bus = fake_bus

    comm.read_command(0x0050, 2)
    assert fake_bus.sent[-1][0] == 0x000C0500
    assert fake_bus.sent[-1][1] == [0x50, 0x00]

    comm.write_command(0x0000, 0x01, 1)
    assert fake_bus.sent[-1][0] == 0x000C0103
    assert fake_bus.sent[-1][1] == [0x01]


def test_eeprom_status_latches_first_detected_value():
    log = LogExporter(DummyMQTT())

    log.set_eeprom_status(True)
    log.set_eeprom_status(False)
    assert log.eeprom_status["present"] is True
    assert log.get_last_log()["eeprom-status"]["present"] is True


def test_eeprom_window_is_large_enough_for_full_session_log():
    assert EEPROM_WINDOW_END >= 4096
