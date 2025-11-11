#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Connect to an Ovum heatpump via VNC and extract data from the Mira user interface.
Adjust CONFIG below to your needs.

Check here for more details:
https://github.com/Schneydr/Mira2mqtt

@author Schneydr
@date 2025/11/9
"""

import os

from MiraDataCollector import MiraDataCollector

"""Debug output"""
DEBUG_OUTPUT = True

"""Write pre-processed region images used for OCR for debugging purposes"""
DEBUG_IMAGE_WRITING = True

"""Configuration"""
CONFIG = {
    'OvumHostname': '192.168.123.45',
    'OvumVNCPort': 5900,
    'OCRLanguage': 'deu',
    'TesseractPath': '/usr/bin/tesseract',
    'mqttUsage': False,
    'mqttBroker': 'hera.cbshome.de',
    'mqttPort': 1883,
    'mqttClientId': 'MiraDataCollector',
    'mqttUser': 'mira',
    'mqttPassword': 'pleasechangeme',
    'mqttTopicPrefix': 'ovum/',
    'mqttStatusTopic': 'status',
    'mqttInfoTopic': 'info',
    'HomeButtonCoordinates': [10, 10],
    'Pages': {
        'Home': {
            'MouseMovesAndClicks': None,
            'MandatoryText': ('Wärmepumpen', 'Netzleistung', 'Umwelt'),
            'Regions': {
                'OutdoorTemp': {
                    'secondaryKey': 'OutdoorTempCurrent',
                    'coordinates': (50, 80, 195, 100),
                    'preProcessing': 'contrast+invert+denoise',
                    'ocrConfig': '--oem 3 --psm 6' },
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
                'HotWaterTarget': {
                    'coordinates': (60, 806, 558, 835),
                    'preProcessing': 'contrast+invert+denoise',
                    'ocrConfig': '--oem 3 --psm 6'},
            }
        },
        'Statistics': {
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
                    'ocrConfig': '--oem 3 --psm 6'},
                'HotWaterEnergy': {
                    'coordinates': (66, 870, 160, 900),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6'},
                'NetworkEnergy': {
                    'coordinates': (310, 836, 400, 866),
                    'preProcessing': 'contrast+invert',
                    'ocrConfig': '--oem 3 --psm 6'}
            }
        }
    }
}

#OvumMiraVNCConnector().main()
os.environ["DEBUG_OUTPUT"] = "1" if DEBUG_OUTPUT else "0"
os.environ["DEBUG_IMAGE_WRITING"] = "1" if DEBUG_IMAGE_WRITING else "0"

mira = MiraDataCollector(CONFIG)
mira.connect_mqtt()
mira.vnc_connect()
mira.traverse_pages()
mira.vnc_disconnect()
