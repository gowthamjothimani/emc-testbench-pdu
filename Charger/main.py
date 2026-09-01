import json
import time
from .NPB import NPB_Charger

charger = NPB_Charger(channel="can1", address=0x03)
def publish_charger_data(data: dict):
    message = json.dumps(data)
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

