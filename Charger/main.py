import json
import time
import paho.mqtt.client as mqtt
from .NPB import NPB_Charger

mqtt_broker = "10.30.250.241"
mqtt_port = 1883    
mqtt_topic = "rnd/rdu03/charger_data"

mqtt_client = mqtt.Client()
mqtt_client.connect(mqtt_broker, mqtt_port, 60)

charger = NPB_Charger(channel="can1", address=0x03)

def publish_charger_data(data: dict):
    message = json.dumps(data)
    mqtt_client.publish(mqtt_topic, message)

if charger.start_device():
    try:
        while True:
            data = charger.read_data()
            print(json.dumps(data, indent=4))
            publish_charger_data(data)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        charger.stop_device()
else:
    print("Could not initialize charger: %s", charger.status)

