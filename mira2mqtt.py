#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Connect to an Ovum heatpump via VNC and extract data from the Mira user interface.
Adjust CONFIG below to your needs.

Check here for more details:
https://github.com/Schneydr/Mira2mqtt

@author Schneydr
@date 2025/11/11
"""

import os

from MiraDataCollector import MiraDataCollector

"""Debug output"""
DEBUG_OUTPUT = True

"""Write pre-processed region images used for OCR for debugging purposes"""
DEBUG_IMAGE_WRITING = True

"""Configuration"""
CONFIG = {
    # Heat pump connection data
    'OvumHostname': '192.168.178.157',
    'OvumVNCPort': 5900,

    # OCR language and locale must match the language setting in Mira
    'OCRLanguage': 'deu',
    'locale': 'de_DE.UTF-8',

    # Path to the tesseract binary
    'TesseractPath': '/usr/bin/tesseract',

    # MQTT configuration
    'mqttUsage': True,
    'mqttBroker': '192.168.178.29',
    'mqttPort': 1883,
    'mqttClientId': 'MiraDataCollector',
    'mqttUser': '',
    'mqttPassword': '',
    'mqttStatusTopic': 'mira2mqtt/Ovum_AC208P/sensors',

    # MQTT auto discovery - experimental
    'mqttAutoDiscovery': False,
    'mqttAutoDiscoveryTopic': 'homeassistant/climate/41fe3f98401a/%s/config',
    # Template used for auto discovery messages
    'autoDiscoveryTemplate': {
        "stat_t": "mira2mqtt/41fe3f98401a/state",
        "name": "",
        "uniq_id": "",
        "dev_cla": "",
        "state_class": "",
        "unit_of_meas": "",
        "val_tpl": "",
        'device': {
            'ids': ['41fe3f98401a'],
            #'ids': ['0024bd0684ff'],
            'mf': 'Ovum',
            'mdl': 'AC208P',
            'name': 'Ovum AC208P',
            'via_device': 'mira2mqtt',
        },
    },

    # For debugging, you can set to True to inspect screenshots
    'DebugKeepScreenshots': False,
    # For debugging, you can set to False to keep region images even
    # after text could be retrieved successfully
    'DebugDeleteImageAfterSuccess': True,

    # Pages we want to access in the Mira UI
    # For each page we define a unique name followed by the page configuration.
    'Pages': {
        'Home': {
            # For each page we need to define how we can access the page
            # by setting coordinates where we will "click".
            'MouseMovesAndClicks': [
                # x and y coordinates
                {'moveTo': [10,10],
                 # optional list of mandatory text we will check the page content for.
                 'MandatoryText': ['Wärmepumpe','Netz']}
            ],
            # Within the page we now need to define at least one region
            # where we want to retrieve data
            'Regions': {
                # Key of the region, must be unique over all pages and regions
                'OutdoorTemp': {
                    # Optionally, you can define additional keys in case we want to
                    # retrieve further data which follows the primary data.
                    'valueSeparators': r'\(',
                    'additionalKeys': 'OutdoorTempCurrent',
                    # Coordinates of the region
                    # x/y top left and x/y bottom right
                    'coordinates': (50, 80, 195, 100),
                    # Optional pre-processing needed for OCR
                    # (grayscale is always performed).
                    # You can choose from the following options. You can also use several
                    # options by combining them with the “+” sign:
                    #   contrast
                    #   invert
                    #   denoise
                    #   thresh -> adaptive thresholding
                    'preProcessing': 'contrast',
                    # tesseract OCR configuration to enhance data retrieval
                    'ocrConfig': '--oem 3 --psm 6',
                    # optional check for decimal places (sometimes the OCR looses th decimal
                    # point) -> value gets corrected by shifting the decimal point
                    'mandatoryDecimalPlaces': 1,
                    # Home Assistant auto discovery
                    'deviceClass': 'temperature',
                    'unit': '°C',
                    'valueTemplate': ['{{ value_json.OutdoorTemp }}', '{{ value_json.OutdoorTempCurrent }}'],
                },
                'NetworkPower': {
                    'coordinates': (10, 250, 110, 290),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'mandatoryDecimalPlaces': 1,
                    # Home Assistant auto discovery
                    'deviceClass': 'power',
                    'unit': 'W',
                    'valueTemplate': '{{ value_json.NetworkPower | float | round(1) }}',
                },
                'Battery': {
                    'coordinates': (38, 523, 112, 550),
                    'preProcessing': 'contrast',
                    'ocrConfig': '--oem 3 --psm 6',
                    # Home Assistant auto discovery
                    'deviceClass': 'battery',
                    'unit': '%',
                    'valueTemplate': '{{ value_json.Battery | float | round(1) }}',
                },
                'HeatingPower': {
                    'coordinates': (168, 523, 260, 550),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    # Home Assistant auto discovery
                    'deviceClass': 'power',
                    'unit': 'W',
                    'valueTemplate': '{{ value_json.HeatingPower | float | round(1) }}',
                },
                'PVPower': {
                    'coordinates': (310, 523, 440, 550),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'mandatoryDecimalPlaces': 1,
                    # Home Assistant auto discovery
                    'deviceClass': 'power',
                    'unit': 'W',
                    'valueTemplate': '{{ value_json.PvPower | float | round(1) }}',
                },
                'HousePower': {
                    'coordinates': (470, 523, 580, 550),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    # Home Assistant auto discovery
                    'deviceClass': 'power',
                    'unit': 'W',
                    'valueTemplate': '{{ value_json.HousePower | float | round(1) }}',
                },
                'HeatingTemp': {
                    'coordinates': (154, 704, 248, 732),
                    'preProcessing': 'gray',
                    'ocrConfig': '',
                    # Home Assistant auto discovery
                    'deviceClass': 'temperature',
                    'unit': '°C',
                    'valueTemplate': '{{ value_json.HeatingTemp }}',
                },
                'HeatingMode': {
                    'coordinates': (60, 728, 558, 758),
                    'valueSeparators': r'\(|\) -',
                    'additionalKeys': ['HeatingTargetTemp', 'HeatingRequirement'],
                    'preProcessing': 'contrast',
                    'ocrConfig': '--oem 3 --psm 6',
                    # Home Assistant auto discovery
                    'deviceClass': ['None', 'temperature', 'None'],
                    'unit': ['None', '°C', 'None'],
                    'valueTemplate': ['{{ value_json.HeatingMode }}',
                                      '{{ value_json.HeatingTargetTemp }}',
                                      '{{ value_json.HeatingRequirement }}'],
                },
#                'HotWaterTemp': {
#                    'coordinates': (205, 770, 305, 808),
#                    'preProcessing': 'contrast+invert',
#                    'ocrConfig': '--oem 3 --psm 6',
#                    # Home Assistant auto discovery
#                    'deviceClass': 'temperature',
#                    'unit': '°C',
#                    'valueTemplate': '{{ value_json.HotWaterTemp }}',
#                },
#                'HotWaterMode': {
#                    'coordinates': (60, 806, 558, 835),
#                    'valueSeparators': r'\(|\) -',
#                    'additionalKeys': 'HotWaterTargetTemp',
#                    'preProcessing': 'contrast+invert+denoise+thresh',
#                    'ocrConfig': '--oem 3 --psm 6',
#                    # Home Assistant auto discovery
#                    'deviceClass': ['None', 'temperature', 'None'],
#                    'unit': ['None', '°C', 'None'],
#                    'valueTemplate': ['{{ value_json.HotWaterMode }}',
#                                      '{{ value_json.HotWaterTargetTemp }}'],
#                },
            }
        },
        'Statistics': {
            # In order to retrieve the data we need, it is sometimes
            # necessary to perform a long sequence of mouse clicks.
            'MouseMovesAndClicks': [
                {'moveTo': [450,960],
                 'MandatoryText': ['Wärmepumpe','Heizen','Warmwasser','Statistik']},
                {'moveTo': [360, 410],
                 'MandatoryText': ['Wärmeautarkie','Wärmepumpe','Energiebilanz']},
            ],
            'Regions': {
                'HeatingEnergy': {
                    # Now, this a little bit tricky:
                    # If there was no hot water production on a day, the heating energy production
                    # is shown where normally the hot water energy production is shown.
                    # Otherwise, the heating energy is shown above the hot water energy.
                    'coordinates': (66, 836, 160, 900),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'decpt': '.',
                    'defaultToZero': True,
                    # Home Assistant auto discovery
                    'deviceClass': 'energy',
                    'unit': 'kWh',
                    'valueTemplate': '{{ value_json.HeatingEnergy | float | round (1) }}',
                },
#                'HotWaterEnergy': {
#                    'coordinates': (66, 870, 270, 900),
#                    'preProcessing': 'contrast+invert',
#                    'ocrConfig': '--oem 3 --psm 6',
#                    'maxValue': 50,
#                    'decpt': '.',
#                    'MandatoryText': 'Warmwasser',
#                    'defaultToZero': True,
#                    # Home Assistant auto discovery
#                    'deviceClass': 'energy',
#                    'unit': 'kWh',
#                    'valueTemplate': '{{ value_json.HotWaterEnergy | float | round (1) }}',
#                },
                'NetworkEnergy': {
                    'coordinates': (310, 836, 400, 900),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'decpt': '.',
                    'defaultToZero': True,
                    # Home Assistant auto discovery
                    'deviceClass': 'energy',
                    'unit': 'kWh',
                    'valueTemplate': '{{ value_json.NetworkEnergy | float | round (1) }}',
                }
            }
        },
        'StatisticsWithDefrosting': {
            # Now we want the daily statistics to show the power
            # consumption to take defrosting into account.
            'MouseMovesAndClicks': [
                {'moveTo': [540, 210],
                 'MandatoryText': ['Abtauen']},
                {'moveTo': [335, 345]}
            ],
            'Regions': {
                'NetworkEnergyWithDefrosting': {
                    'coordinates': (310, 836, 400, 900),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'decpt': '.',
                    'defaultToZero': True,
                    # Home Assistant auto discovery
                    'deviceClass': 'energy',
                    'unit': 'kWh',
                    'valueTemplate': '{{ value_json.NetworkEnergyWithDefrosting | float | round (1) }}',
                }
            }
        },
        'Buffer':{
            'MouseMovesAndClicks': [
                {'moveTo': [50, 110],
                 'MandatoryText': ['Wärmepumpe','Puffer']},
                {'moveTo': [500, 230],
                 'MandatoryText': ['Puffer', 'HEIZKREISE']},
            ],
            'Regions': {
                'Buffer_IST': {
                    'coordinates': (425, 770, 520, 800),
                    'preProcessing': 'contrast',
                    'ocrConfig': '--oem 3 --psm 6',
                    'mandatoryDecimalPlaces': 1,
                    # Home Assistant auto discovery
                    'deviceClass': 'temperature',
                    'unit': '°C',
                    'valueTemplate': '{{ value_json.Buffer_IST_temperature }}',
                },
                'Buffer_SOLL': {
                    'coordinates': (425, 865, 520, 895),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'mandatoryDecimalPlaces': 1,
                    # Home Assistant auto discovery
                    'deviceClass': 'temperature',
                    'unit': '°C',
                    'valueTemplate': '{{ value_json.Buffer_SOLL_temperature }}',
                }
            }
        },
        'UnderfloorHeating': {
            'MouseMovesAndClicks': [
                {'moveTo': [50,110],
                 'MandatoryText': ['Wärmepumpe','Heizen']},
                {'moveTo': [230, 230],
                 'MandatoryText': ['FUSSBODENHEIZUNG']},
            ],
            'Regions': {
                'Heating_SOLL': {
                    'coordinates': (325, 435, 420, 465),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'mandatoryDecimalPlaces': 1,
                    # Home Assistant auto discovery
                    'deviceClass': 'temperature',
                    'unit': '°C',
                    'valueTemplate': '{{ value_json.Heating_SOLL | float | round (1) }}',
                },
                'Heating_IST': {
                    'coordinates': (325, 520, 420, 550),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'mandatoryDecimalPlaces': 1,
                    # Home Assistant auto discovery
                    'deviceClass': 'temperature',
                    'unit': '°C',
                    'valueTemplate': '{{ value_json.Heating_IST | float | round (1) }}',
                }
            }
        },
        'BackHome': {
            'MouseMovesAndClicks': [
                # x and y coordinates
                {'moveTo': [10, 10],
                 # optional list of mandatory text we will check the page content for.
                 'MandatoryText': ['Wärmepumpe','Netz']}
            ],
            'Regions': {
            }
        }
    }
}

os.environ["DEBUG_OUTPUT"] = "1" if DEBUG_OUTPUT else "0"
os.environ["DEBUG_IMAGE_WRITING"] = "1" if DEBUG_IMAGE_WRITING else "0"

mira = MiraDataCollector(CONFIG)
mira.connect_mqtt()
mira.vnc_connect()
mira.traverse_pages()
mira.vnc_disconnect()
