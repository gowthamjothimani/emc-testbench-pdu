"""
MQTT client - same connect/publish/config pattern as the ACU testbench,
plus a lightweight reachability ping (used by the status bar) so the
operator can tell "broker down" apart from "broker up, but this device
can't route to it" (still shows red either way, but the app.py status
thread also uses this to decide the network icon independent of whether
the persistent MQTT session happens to be connected at that instant).
"""
import json
import platform
import socket
import subprocess

import paho.mqtt.client as mqtt

from config import MQTT_DEFAULT_CONFIG, MQTT_PING_TIMEOUT_S


class MQTTClient:
    def __init__(self, socketio):
        self.client = None
        self.socketio = socketio
        self.connected = False
        self.hostname = socket.gethostname()
        self.mqtt_config = dict(MQTT_DEFAULT_CONFIG)

    def on_connect(self, client, userdata, flags, rc):
        self.connected = (rc == 0)
        print("Connected to MQTT Broker" if self.connected else f"MQTT connect failed (rc={rc})")
        self.update_status()

    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        self.update_status()
        print("Disconnected from MQTT Broker")

    def update_status(self):
        color = "lightgreen" if self.connected else "lightcoral"
        self.socketio.emit('mqtt_status', {"color": color, "connected": self.connected})

    def connect_mqtt(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass

        self.client = mqtt.Client()
        if self.mqtt_config.get("username"):
            self.client.username_pw_set(self.mqtt_config["username"], self.mqtt_config["password"])

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        try:
            self.client.connect(self.mqtt_config["hostname"], self.mqtt_config["port"], 60)
            self.client.loop_start()
        except Exception as e:
            print(f"MQTT Connection Error: {e}")
            self.connected = False
            self.update_status()

    def update_config(self, config):
        self.mqtt_config.update(config)
        self.connect_mqtt()

    def publish_data(self, data, topic=None):
        if not self.client:
            print("MQTT publish skipped - client not initialized")
            return
        publish_topic = topic or self.mqtt_config.get("topic")
        payload = json.dumps(data, default=str)
        self.client.publish(publish_topic, payload)

    def ping_broker(self) -> bool:
        """
        Network-level reachability check for the status bar, independent
        of the persistent MQTT session state. Uses the system ping so it
        works even before/if the MQTT client itself hasn't connected yet.
        """
        host = self.mqtt_config.get("hostname")
        if not host:
            return False
        count_flag = "-n" if platform.system().lower() == "windows" else "-c"
        timeout_flag = "-w" if platform.system().lower() == "windows" else "-W"
        timeout_val = str(int(MQTT_PING_TIMEOUT_S * 1000)) if platform.system().lower() == "windows" else str(int(MQTT_PING_TIMEOUT_S) or 1)
        try:
            result = subprocess.run(
                ["ping", count_flag, "1", timeout_flag, timeout_val, host],
                capture_output=True, timeout=MQTT_PING_TIMEOUT_S + 2.0
            )
            return result.returncode == 0
        except Exception:
            return False
