I2C_BUS = 2                     
HDC302X_ADDR = 0x47            
EEPROM_ADDR = 0x50              
MAX7320_ADDR = 0x59             

EEPROM_PAGE_SIZE = 32
EEPROM_WP_GPIO = None           
EEPROM_WINDOW_START = 0x0000
EEPROM_WINDOW_END = 0x0800      

# CAN
CAN_CHANNEL = "can1"          
CAN_BITRATE = 250000
CHARGER_NODE_ADDRESS = 0x03 

PUSHBUTTON_GPIO = "P8_10"
PUSHBUTTON_REQUIRED_PRESSES = 2

#  MQTT 
MQTT_DEFAULT_CONFIG = {
    "hostname": "10.30.250.241",
    "port": 1883,
    "topic": "emc_pdu_test",
    "username": "",
    "password": "",
}
MQTT_PING_TIMEOUT_S = 1.5       

