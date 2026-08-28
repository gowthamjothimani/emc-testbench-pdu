# QHB Address Map Libary
class QHB_ADDRESS_MAP:
    def __init__(self):
        self.NODE_ID = 15
        self.PACK_DATA_1 = 0x18F
        self.PACK_DATA_2 = 0x28F
        self.MAXIMUM_ALLOWED_PACK_VALUES = 0x38F
        self.MAXIMUM_ALLOWED_VALUES = 0x351
        self.VICTRON_BASED_SERVICE = 0x356
        self.GLOBAL_BATTERY_SERVICE_MESSAGES = 0x7FA
        self.INDIVIDUAL_DATA_BASE = 0x48F
        self.INDIVIDUAL_BATTERY_SERVICE_VALUES = 0x600 + self.NODE_ID
        self.SMART_CHARGER_PROTOCOLS = 0x600 + self.NODE_ID
        self.SDO_REQUEST_ID = 0x600 + self.NODE_ID
        self.SDO_RESPONSE_ID = 0x580 + self.NODE_ID
        self.UNIT_PERCENT = "%"
        self.UNIT_VOLT = "V"
        self.UNIT_CURRENT = "A"
        self.UNIT_TEMP = "°C"
        self.TEMP_OFFSET = 55

        # Pack Data 1
        self.PD1_SOC = 0
        self.PD1_VOLTAGE_LSB = 1
        self.PD1_VOLTAGE_MSB = 2
        self.PD1_SoC_ACTIVE_BAT = 5
        self.PD1_ACTIVE_BAT = 6
        self.PD1_PASSIVE_BAT = 7

        # Pack Data 2
        self.PD2_PACK_STATE = 0
        self.PD2_CURRENT_LSB = 1
        self.PD2_CURRENT_MSB = 2
        self.PD2_SMART_CHARGER = 3
        self.PD2_MAX_PACK_SOC = 4
        self.PD2_MIN_PACK_SOC = 5
        self.PD2_MAX_TEMP = 6
        self.PD2_MIN_TEMP = 7

        # Individual Battery Data
        self.IND_PERMISSION = 0
        self.IND_HEATING_MODE = 1
        self.IND_VIRTUAL_ID_PACK = 2
        self.IND_VIRTUAL_ID_CELL = 3
        self.IND_SOC = 4
        self.IND_STATE_OF_BATTERY = 5
        self.IND_CURRENT = 6
        self.IND_TEMP = 7

        # Maximum allowed Values
        self.MAX_CHARGE_VOLT_LSB = 0
        self.MAX_CHARGE_VOLT_MSB = 1
        self.MAX_CHARGE_CURR_LSB = 2
        self.MAX_CHARGE_CURR_MSB = 3
        self.MAX_DISCHARGE_CURR_LSB = 4
        self.MAX_DISCHARGE_CURR_MSB = 5
        self.MAX_DISCHARGE_VOLT_LSB = 6
        self.MAX_DISCHARGE_VOLT_MSB = 7

        # Global Battery Service Messages
        self.RESET_DELAY_TO_JOIN = 0

        # Individual Battery Service Values
        self.BAT_DATA_REQ_CS = 0x40
        self.VENDOR_ID = (24, 16, 1)
        self.PRODUCT_ID = (24, 16, 2)
        self.REVISION_NUMBER = (24, 16, 3)
        self.SERIAL_NUMBER_CIA = (24, 16, 4)
        self.SERIAL_NUMBER = (30, 60, 0)
        self.BATTERY_CAPACITY = (30, 61, 0)
        self.BATTERY_SOH = (30, 62, 0)
        self.CYCLE_COUNT = (30, 63, 0)
        self.DEEP_DISCHARGE = (30, 64, 0)
        self.SUB_ZERO_CHARGERS = (30, 65, 0)
        self.MAX_VOLTAGE = (30, 66, 0)
        self.MIN_VOLTAGE = (30, 70, 0)
        self.HUMIDITY_LEVEL = (30, 67, 0)
        self.MAX_CHARGE = (30, 68, 0)
        self.MAX_DISCHARGE = (30, 69, 0)
        self.MAX_TEMP_SENSOR_1 = (30, 71, 0)
        self.MAX_TEMP_SENSOR_2 = (30, 72, 0)
        self.BASH_COUNTER = (30, 73, 0)
        self.POWER_USED_SINCE_LAST_CHARGE = (30, 74, 0)

        # SMART Charger Protocols
        self.SMART_CHRGE_PROTO_CS = 0x23
        self.SMART_CHRGE_SDO_INDEX_LSB = 10
        self.SMART_CHRGE_SDO_INDEX_MSB = 80
        self.SMART_CHRGE_SDO_SUBINDEX = 0
        self.SMART_CHRGE_PERMISSION_TO_JOIN = 4
        self.SMART_CHRGE_JOIN_VALUE_FALSE = 0
        self.SMART_CHRGE_JOIN_VALUE_TRUE = 1
        self.SMART_CHRGE_SDO_DATA_1 = 5
        self.SMART_CHRGE_SDO_DATA_2 = 6
        self.SMART_CHRGE_SDO_DATA_3 = 7

        #BAT LED flash while charging
        self.BAT_LED_FLASH_CS = 0x23
        self.BAT_LED_FLASH_SDO_INDEX_LSB = 10
        self.BAT_LED_FLASH_SDO_INDEX_MSB = 77
        self.BAT_LED_FLASH_SUBINDEX = 0
        self.BAT_LED_FLASH_SDO_DATA_0 = 4
        self.BAT_LED_FLASH_SDO_DATA_1 = 5
        self.BAT_LED_FLASH_SDO_DATA_2 = 6
        self.BAT_LED_FLASH_SDO_DATA_3 = 7

        #BAT LED sequence activation
        self.BAT_LED_SEQ_CS = 0x23
        self.BAT_LED_SEQ_SDO_INDEX_LSB = 10
        self.BAT_LED_SEQ_SDO_INDEX_MSB = 45 
        self.BAT_LED_SEQ_SUBINDEX = 0
        self.BAT_LED_SEQ_SDO_DATA_0 = 4
        self.BAT_LED_SEQ_SDO_DATA_1 = 5
        self.BAT_LED_SEQ_SDO_DATA_2 = 6
        self.BAT_LED_SEQ_SDO_DATA_3 = 7
        self.LED_Interval = (0,255)
        self.LED_SEQ_DURATION = (0,255)

        #Permission To Join Pack
        self.JOIN_PACK_SEQ_CS = 0x23
        self.JOIN_PACK_SDO_INDEX_LSB = 10
        self.JOIN_PACK_SDO_INDEX_MSB = 55
        self.JOIN_PACK_SUBINDEX = 0
        self.JOIN_PACK_SDO_DATA_0 = 4
        self.JOIN_PACK_SDO_DATA_1 = 5
        self.JOIN_PACK_SDO_DATA_2 = 6
        self.JOIN_PACK_SDO_DATA_3 = 7

        #CAN Baudrate
        self.CAN_BAUDRATE_SEQ_CS = 0x23
        self.CAN_BAUDRATE_SDO_INDEX_LSB = 10
        self.CAN_BAUDRATE_SDO_INDEX_MSB = 75
        self.CAN_BAUDRATE_SUBINDEX = 0
        self.CAN_BAUDRATE_SDO_DATA_0 = 4
        self.CAN_BAUDRATE_SDO_DATA_1 = 5
        self.CAN_BAUDRATE_SDO_DATA_2 = 6
        self.CAN_BAUDRATE_SDO_DATA_3 = 7

        #SET storage bytes
        self.SET_STORAGE_SEQ_CS = 0x23
        self.SET_STORAGE_SDO_INDEX_LSB = 10
        self.SET_STORAGE_SDO_INDEX_MSB = 95
        self.SET_STORAGE_SUBINDEX = 0
        self.SET_STORAGE_SDO_DATA_0 = 4
        self.SET_STORAGE_SDO_DATA_1 = 5
        self.SET_STORAGE_SDO_DATA_2 = 6
        self.SET_STORAGE_SDO_DATA_3 = 7

        # Battery Heating Activation
        self.HEATING_ACT_CS = 0x23
        self.HEATING_ACT_SDO_INDEX_LSB = 10
        self.HEATING_ACT_SDO_INDEX_MSB = 35
        self.HEATING_ACT_SUBINDEX = 0
        self.HEATING_ACT_SDO_DATA_0 = 4
        self.HEATING_ACT_SDO_DATA_1 = 5
        self.HEATING_ACT_SDO_DATA_2 = 6
        self.HEATING_ACT_SDO_DATA_3 = 7
    
        #Battery state
        self.BATTERY_STATE = {
            10: "Standby",
            20: "Ready",
            30: "Disengaged",
            40: "Discharging",
            50: "Charging",
            70: "Error"
        }

        #Smart charger protocol
        self.PROTOCOL_TYPE = {
            1:"Victron",
            2:"MeanWell",
            3:"DeltaQ",
            4:"ChineseJ1939",
            5:"Zivan"
        }

        self.PROTOCOL_ON_OFF = {
            0:"OFF",
            1:"ON"
        }

        #Charge LED option
        self.LED_OPTION = {
            0:"No LEDs while charging",
            1:"LEDs rolling while charging",
            2:"LEDs rolling while charging + smart charger",
            3:"LEDs blinking while charging",
            4:"LEDs blinking while charging + smart charger"
        }

        self.LED_SEQ_CHOICE = {
            1:"ALL 5 LEDS ON",
            2:"All 5 LEDs blinking",
            3:"Outside to Inside blinking",
            4:"Kinight rider"
        }

        self.PERMISSION_TO_JOIN = {
            0:"false",
            1:"true"
        }

        self.BAUD_RATE = {
            1:"125kbps",
            2:"250kbps",
            3:"500kbps",
            4:"1000kbps"
        }
      
        self.STORAGE_BYTE_LSB = (0,255)
        self.STORAGE_BYTE_MSB = (0,255)

        self.HEATING_MODE = {
            0: "Mode 0",
            1: "Mode 1",
            2: "Mode 2",
            3: "Mode 3",
            4: "Mode 4"
        }