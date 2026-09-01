from log_exporter import LogExporter


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
