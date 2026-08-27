import can
import datetime
import json
import threading
import struct
import time
import paho.mqtt.client as mqtt
from Battery.qhb import CAN_QHB
from Battery.qhb_address import QHB_ADDRESS_MAP

mqtt_broker = "10.30.250.241"
mqtt_port = 1883    
mqtt_topic = "rnd/rdu03/battery_data"

mqtt_client = mqtt.Client()
mqtt_client.connect(mqtt_broker, mqtt_port, 60)


def publish_charger_data(data: dict):
    message = json.dumps(data)
    mqtt_client.publish(mqtt_topic, message)

node = CAN_QHB()
if node.init_device():
    thread = threading.Thread(target=node.start_device, daemon=True)
    thread.start()

    while True:
        print(json.dumps(node.read_data(), indent=4))
        time.sleep(2)
else:
    print("Failed to initialize CAN device, not starting reader.")