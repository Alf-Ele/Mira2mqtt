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
    'OvumHostname': '192.168.123.45',
    'OvumVNCPort': 5900,

    # OCR language and locale must match the language setting in Mira
    'OCRLanguage': 'deu',
    'locale': 'de_DE.UTF-8',

    # MQTT configuration
    'mqttUsage': False,
    'mqttBroker': 'localhost',
    'mqttPort': 1883,
    'mqttClientId': 'MiraDataCollector',
    'mqttUser': 'mira',
    'mqttPassword': 'pleasechangeme',
    'mqttTopicPrefix': 'ovum/',
    'mqttStatusTopic': 'status',
    'mqttInfoTopic': 'info',

    # Path to the tesseract binary
    'TesseractPath': '/usr/bin/tesseract',

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
                 'MandatoryText': ['Wärmepumpe','Netzleistung','Umwelt']}
            ],
            # Within the page we now need to define at least one region
            # where we want to retrieve data
            'Regions': {
                # Key of the region, must be unique over all pages and regions
                'OutdoorTemp': {
                    # Optionally, you can define a secondary key in case we want to
                    # retrieve secondary data which follows the primary data,
                    # separated by brackets (...)
                    'secondaryKey': 'OutdoorTempCurrent',
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
                    'preProcessing': 'contrast+invert+denoise',
                    # tesseract OCR configuration to enhance data retrieval
                    'ocrConfig': '--oem 3 --psm 6' ,
                    # optional maximum value, which when exceeding lead to the value
                    # being corrected by shifting the decimal point
                    'maxValue': 50,
                },
                'NetworkPower': {
                    'coordinates': (10, 250, 110, 290),
                    'preProcessing': 'contrast+invert+denoise+thresh',
                    'ocrConfig': '--oem 3 --psm 6'},
                'NetworkPower2': {
                    'coordinates': (250, 502, 350, 522),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6'},
                'Environment': {
                    'coordinates': (490, 260, 590, 290),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': ''},
                'HeatPump': {
                    'coordinates': (240, 523, 360, 550),
                    'preProcessing': 'contrast+invert+denoise+thresh',
                    'ocrConfig': '--oem 3 --psm 6'},
                'HeatingActual': {
                    'coordinates': (154, 704, 248, 732),
                    'preProcessing': 'gray',
                    'ocrConfig': ''},
                'HeatingTarget': {
                    'coordinates': (60, 730, 558, 762),
                    'preProcessing': 'contrast+invert+denoise',
                    'ocrConfig': '--oem 3 --psm 6' },
                'HotWaterActual': {
                    'coordinates': (205, 770, 305, 808),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': ''},
                'HotWaterMode': {
                    'coordinates': (60, 806, 558, 835),
                    'secondaryKey': 'HotWaterTarget',
                    'preProcessing': 'contrast+invert+denoise+thresh',
                    'ocrConfig': '--oem 3 --psm 6'},
            }
        },
        'Statistics': {
            # In order to retrieve the data we need, it is sometimes
            # necessary to perform a long sequence of mouse clicks.
            # Here we want to access the daily statistics, and we want
            # the power consumption to take defrosting into account.
            'MouseMovesAndClicks': [
                {'moveTo': [450,960],
                 'MandatoryText': ['Wärmepumpe','Heizen','Warmwasser','Statistik']},
                {'moveTo': [230, 410],
                 'MandatoryText': ['Wärmeautarkie','Wärmepumpe','Energiebilanz']},
                {'moveTo': [540, 210],
                 'MandatoryText': ['Abtauen']},
                {'moveTo': [335, 345]},
                {'moveTo': [335, 400]}
            ],
            'Regions': {
                'HeatingEnergy': {
                    'coordinates': (66, 836, 160, 866),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'decpt': '.'},
                'HotWaterEnergy': {
                    'coordinates': (66, 870, 160, 900),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'decpt': '.'},
                'NetworkEnergy': {
                    'coordinates': (310, 836, 400, 866),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6',
                    'decpt': '.'}
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
