class ChargerAddress:
    def __init__(self):
        self.charger_to_controller_base = 0x000C0000
        self.controller_to_charger_base = 0x000C0100
        self.broadcast_id = 0x000C01FF

        self.default_channel = "can1"
        self.default_bitrate = 250000          # bps, fixed by spec (CAN ISO-11898)
        self.frame_is_extended = True          # 29-bit identifier / CAN 2.0B
        self.default_timeout_sec = 1.0
        self.default_retry_count = 3
        self.min_request_period_ms = 20     
        self.max_response_time_ms = 5          

        # Operation Control
        self.OPERATION = 0x0000             

        self.OPERATION_OFF = 0x00
        self.OPERATION_ON = 0x01
        self.operation_state_map = {
            0x00: "OFF",
            0x01: "ON",
        }

        # Configured Output
        self.VOUT_SET = 0x0020                 
        self.IOUT_SET = 0x0030                 

        # Operating Data (live measurements)
        self.READ_VIN = 0x0050                
        self.READ_VOUT = 0x0060                
        self.READ_IOUT = 0x0061                
        self.READ_TEMPERATURE_1 = 0x0062      

        # Identification
        self.MFR_ID_B0B5 = 0x0080             
        self.MFR_ID_B6B11 = 0x0081            
        self.MFR_MODEL_B0B5 = 0x0082           
        self.MFR_MODEL_B6B11 = 0x0083          
        self.MFR_REVISION_B0B5 = 0x0084        
        self.MFR_LOCATION_B0B2 = 0x0085        
        self.MFR_DATE_B0B5 = 0x0086            
        self.MFR_SERIAL_B0B5 = 0x0087        
        self.MFR_SERIAL_B6B11 = 0x0088        

        # Charging Curve Configuration
        self.CURVE_CC = 0x00B0               
        self.CURVE_CV = 0x00B1            
        self.CURVE_FV = 0x00B2                
        self.CURVE_TC = 0x00B3                
        self.CURVE_CONFIG = 0x00B4             
        self.CURVE_CC_TIMEOUT = 0x00B5        
        self.CURVE_CV_TIMEOUT = 0x00B6        
        self.CURVE_FV_TIMEOUT = 0x00B7         
        self.CHG_STATUS = 0x00B8               
        self.CHG_RST_VBAT = 0x00B9             

        
        # System
        self.FAULT_STATUS = 0x0040             
        self.SCALING_FACTOR = 0x00C0         
        self.SYSTEM_STATUS = 0x00C1           
        self.SYSTEM_CONFIG = 0x00C2            

        self.size = {
            self.OPERATION: 1,
            self.VOUT_SET: 2,
            self.IOUT_SET: 2,
            self.FAULT_STATUS: 2,
            self.READ_VIN: 2,
            self.READ_VOUT: 2,
            self.READ_IOUT: 2,
            self.READ_TEMPERATURE_1: 2,
            self.MFR_ID_B0B5: 6,
            self.MFR_ID_B6B11: 6,
            self.MFR_MODEL_B0B5: 6,
            self.MFR_MODEL_B6B11: 6,
            self.MFR_REVISION_B0B5: 6,
            self.MFR_LOCATION_B0B2: 6,
            self.MFR_DATE_B0B5: 6,
            self.MFR_SERIAL_B0B5: 6,
            self.MFR_SERIAL_B6B11: 6,
            self.CURVE_CC: 2,
            self.CURVE_CV: 2,
            self.CURVE_FV: 2,
            self.CURVE_TC: 2,
            self.CURVE_CONFIG: 2,
            self.CURVE_CC_TIMEOUT: 2,
            self.CURVE_CV_TIMEOUT: 2,
            self.CURVE_FV_TIMEOUT: 2,
            self.CHG_STATUS: 2,
            self.CHG_RST_VBAT: 2,
            self.SCALING_FACTOR: 2,
            self.SYSTEM_STATUS: 2,
            self.SYSTEM_CONFIG: 2,
        }

        self.scale = {
            self.OPERATION: None,
            self.VOUT_SET: 0.01,
            self.IOUT_SET: 0.01,
            self.FAULT_STATUS: None,
            self.READ_VIN: 0.1,
            self.READ_VOUT: 0.01,
            self.READ_IOUT: 0.01,
            self.READ_TEMPERATURE_1: 0.1,
            self.CURVE_CC: 0.01,
            self.CURVE_CV: 0.01,
            self.CURVE_FV: 0.01,
            self.CURVE_TC: 0.01,
            self.CURVE_CONFIG: None,
            self.CURVE_CC_TIMEOUT: None,
            self.CURVE_CV_TIMEOUT: None,
            self.CURVE_FV_TIMEOUT: None,
            self.CHG_STATUS: None,
            self.CHG_RST_VBAT: 0.01,
            self.SCALING_FACTOR: None,
            self.SYSTEM_STATUS: None,
            self.SYSTEM_CONFIG: None,
        }
        self.fault_mapper = [
            {"charger_fault_code": 1, "fault_message": "OTP - Over Temperature Protection",
             "application_code": "CHG1001"},
            {"charger_fault_code": 2, "fault_message": "OVP - Output Over Voltage Protection",
             "application_code": "CHG1002"},
            {"charger_fault_code": 3, "fault_message": "OLP - Output Over Current Protection",
             "application_code": "CHG1003"},
            {"charger_fault_code": 4, "fault_message": "SHORT - Output Short Circuit Protection",
             "application_code": "CHG1004"},
            {"charger_fault_code": 5, "fault_message": "AC_FAIL - AC Input Abnormal",
             "application_code": "CHG1005"},
            {"charger_fault_code": 6, "fault_message": "OP_OFF - Output Turned Off",
             "application_code": "CHG1006"},
        ]
        self.system_status_mapper = [
            {"charger_fault_code": 1, "fault_message": "DC_OK - DC Output Normal",
             "application_code": "CHG3001"},
            {"charger_fault_code": 5, "fault_message": "INITIAL_STATE - Unit In Initial Stage",
             "application_code": "CHG3002"},
            {"charger_fault_code": 6, "fault_message": "EEPER - EEPROM Access Error",
             "application_code": "CHG3003"},
        ]
        self.chg_status_mapper = [
            {"charger_fault_code": 0, "byte": "low", "fault_message": "FULLM - Battery Fully Charged",
             "application_code": "CHG2001"},
            {"charger_fault_code": 1, "byte": "low", "fault_message": "CCM - Constant Current Mode",
             "application_code": "CHG2002"},
            {"charger_fault_code": 2, "byte": "low", "fault_message": "CVM - Constant Voltage Mode",
             "application_code": "CHG2003"},
            {"charger_fault_code": 3, "byte": "low", "fault_message": "FVM - Float Mode",
             "application_code": "CHG2004"},
            {"charger_fault_code": 6, "byte": "low", "fault_message": "WAKEUP_STOP - Wake-up Unfinished",
             "application_code": "CHG2005"},
            {"charger_fault_code": 7, "byte": "low", "fault_message": "HI_TEMP - Internal High Temperature",
             "application_code": "CHG2006"},
            {"charger_fault_code": 2, "byte": "high", "fault_message": "NTCER - Temperature Compensation Circuit Error",
             "application_code": "CHG2007"},
            {"charger_fault_code": 3, "byte": "high", "fault_message": "BTNC - No Battery Detected",
             "application_code": "CHG2008"},
            {"charger_fault_code": 5, "byte": "high", "fault_message": "CCTOF - Constant Current Mode Timeout",
             "application_code": "CHG2009"},
            {"charger_fault_code": 6, "byte": "high", "fault_message": "CVTOF - Constant Voltage Mode Timeout",
             "application_code": "CHG2010"},
            {"charger_fault_code": 7, "byte": "high", "fault_message": "FVTOF - Float Mode Timeout",
             "application_code": "CHG2011"},
        ]
        self.curve_config_mapper = [
            {"charger_fault_code": 7, "byte": "low",
             "fault_message": "CUVE - Charge Curve Function (0=PSU mode, 1=Charger mode)",
             "application_code": "CHG4001"},
            {"charger_fault_code": 0, "byte": "high",
             "fault_message": "CVTOE - Constant Voltage Timeout Enable",
             "application_code": "CHG4002"},
            {"charger_fault_code": 1, "byte": "high",
             "fault_message": "CCTOE - Constant Current Timeout Enable",
             "application_code": "CHG4003"},
            {"charger_fault_code": 3, "byte": "high",
             "fault_message": "RSTE - Restart Charge After Full Enable",
             "application_code": "CHG4004"},
        ]
        self.model_defaults = {
            "model": "NPB-1200-48",
            "boost_voltage_v": 57.6,
            "float_voltage_v": 55.2,
            "voltage_adjustable_range_v": (42.0, 80.0),
            "rated_output_current_a": 18.0,
            "current_adjustable_range_pct": (50, 100),
            "max_power_w": 1209.6,
            "recommended_battery_capacity_ah": (60, 210),
        }