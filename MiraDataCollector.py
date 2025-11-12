"""
Connect to an Ovum heatpump via VNC and extract data from the Mira user interface.

Check here for more details:
https://github.com/Schneydr/Mira2mqtt

@author Schneydr
@date 2025/11/11
"""

import datetime
import locale
import logging
import os
import time
import cv2
import pytesseract
import json
import paho.mqtt.client as mqtt

from vncdotool import api
from PIL import Image
from MiraRegion import MiraRegion


class MiraDataCollector:
    DEBUG_OUTPUT = False
    DEBUG_IMAGE_WRITING = False

    hostname: str = None
    vncport: int = 5900
    vncclient: api = None
    config: dict = None
    timestamp: datetime = None
    data: dict = None
    screenshot_path: str = None
    mqtt_client: mqtt = None
    mqtt_connection_etablished = False
    unacked_publish = None

    # MQTT defaults
    FIRST_RECONNECT_DELAY = 1
    RECONNECT_RATE = 2
    MAX_RECONNECT_COUNT = 12
    MAX_RECONNECT_DELAY = 60


    def __init__(self, config: dict):
        """
        Constructor.
        :param config: Configuration object
        """
        self.config = config

        # Init data
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self.data = {'timestamp': self.timestamp}

        if "DEBUG_OUTPUT" in os.environ and os.environ["DEBUG_OUTPUT"] == "1":
            self.DEBUG_OUTPUT = True

        if "DEBUG_IMAGE_WRITING" in os.environ and os.environ["DEBUG_IMAGE_WRITING"] == "1":
            self.DEBUG_IMAGE_WRITING = True
    # end __init__()

    def __enter__(self):
        self.vnc_connect()
    # end __enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Destructor. Close existing VNC session.
        :param exc_type:
        :param exc_val:
        :param exc_tb:
        :return:
        """
        if self.vncclient is not None:
            self.vnc_disconnect()
    # end __exit__()

    def connect_mqtt(self) -> None:
        if 'mqttUsage' in self.config and not self.config['mqttUsage']:
            return
        #def on_connect(client, userdata, flags, rc):
        #    # For paho-mqtt 2.0.0, you need to add the properties parameter.
        #    # def on_connect(client, userdata, flags, rc, properties):
        #    if rc == 0:
        #        self.mqtt_connection_etablished = True
        #        print("Connected to MQTT Broker!")
        #    else:
        #        print("Failed to connect, return code %d\n", rc)

        print("Connect to MQTT Broker...")
        self.unacked_publish = set()

        # Set Connecting Client ID
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        # Connect
        mqttc.username_pw_set(self.config['mqttUser'], self.config['mqttPassword'])
        mqttc.connect(self.config['mqttBroker'], self.config['mqttPort'])
        mqttc.loop_start()
        self.mqtt_client = mqttc
        print("Connected to MQTT Broker!")
    # end connect_mqtt()

    def on_disconnect(self, userdata, rc):
        logging.info("Disconnected with result code: %s", rc)
        reconnect_count, reconnect_delay = 0, self.FIRST_RECONNECT_DELAY
        while reconnect_count < self.MAX_RECONNECT_COUNT:
            logging.info("Reconnecting in %d seconds...", reconnect_delay)
            time.sleep(reconnect_delay)

            try:
                self.mqtt_client.reconnect()
                logging.info("Reconnected successfully!")
                return
            except Exception as err:
                logging.error("%s. Reconnect failed. Retrying...", err)

            reconnect_delay *= self.RECONNECT_RATE
            reconnect_delay = min(reconnect_delay, self.MAX_RECONNECT_DELAY)
            reconnect_count += 1
        logging.info("Reconnect failed after %s attempts. Exiting...", reconnect_count)
    # end on_disconnect()

    def mqtt_publish(self, topic: str, message: str):
        if 'mqttUsage' in self.config and not self.config['mqttUsage']:
            return

        # Publish message
        msg_info = self.mqtt_client.publish(topic, message)
        self.unacked_publish.add(msg_info.mid)
        msg_info.wait_for_publish()

        # Disconnect from broker
        self.mqtt_client.disconnect()
        self.mqtt_client.loop_stop()
    # end mqtt_publish()

    def publish_data(self):
        data = self.data

        # Set locale for parsing localized values
        locale.setlocale(locale.LC_ALL, self.config['locale'])

        # Cleanup and parse numeric data before publishing
        for key, value in data.items():
            if str(value).endswith(" kWh"):
                value = str(value).removesuffix(" kWh")
                numvalue = locale.atof(value)
                data[key] = str(numvalue)
            elif str(value).endswith(" MWh"):
                value = str(value).removesuffix(" MWh")
                numvalue = locale.atof(value)
                numvalue *= 1000
                data[key] = str(numvalue)
            elif str(value).endswith(" kW"):
                value = str(value).removesuffix(" kW")
                numvalue = locale.atof(value)
                numvalue *= 1000
                data[key] = str(numvalue)
            elif str(value).endswith(" W"):
                value = str(value).removesuffix(" W")
                numvalue = locale.atof(value)
                data[key] = str(numvalue)
            elif str(value).endswith(" °C"):
                value = str(value).removesuffix(" °C")
                numvalue = locale.atof(value)
                data[key] = str(numvalue)
            else:
                numvalue = str(value)

            if self.DEBUG_OUTPUT and numvalue is not None:
                print (f"Cleaned value for {key} = '{numvalue}'")

        # Publish data
        self.mqtt_publish(self.config['mqttTopicPrefix'] + self.config['mqttInfoTopic'],
                          json.dumps(self.data))
    # end publish_data()

    def vnc_connect(self) -> None:
        # Establish VNC connection
        connection_target = (self.config['OvumHostname'] + '::'
                             + str(self.config['OvumVNCPort']))
        print(f"Connecting to your heat pump on {connection_target}...")

        self.vncclient = api.connect(connection_target)
        time.sleep(1)
    # end vnc_connect()

    def vnc_disconnect(self) -> None:
        self.vncclient.disconnect()
        api.shutdown()
    # end vnc_disconnect()

    def traverse_pages(self) -> None:
        # First move the mouse to wake up the display
        self.vncclient.mouseMove(100, 100)
        time.sleep(0.5)

        for page, page_config in self.config['Pages'].items():
            print("Processing page %s..." % page)
            mira_page = MiraPage(self, page)

            if page_config['MouseMovesAndClicks'] is not None:
                mandatory_found = mira_page.do_mouse_moves_and_click(page_config['MouseMovesAndClicks'])
                if not mandatory_found:
                    continue

            # Skip further processing unless mandatory text was found
            mira_page.take_screenshot()
            if ('MandatoryText' in page_config
                    and not mira_page.check_mandatory_content(page_config['MandatoryText'])):
                continue

            mira_page.process_regions()
            mira_page.delete_screenshot()
            self.data.update(mira_page.data)

        print("\nExtracted values:")
        for k, v in self.data.items():
            print(f"{k}: {v}")

        # Publish data
        self.publish_data()
    # end traverse_pages()

class MiraPage(MiraDataCollector):
    """
    A page in the Mira user interface.
    """

    DEBUG_OUTPUT = False
    DEBUG_IMAGE_WRITING = False

    name: str = None
    img: cv2 = None
    screenshot_path: str = None

    def __init__(self, mira: MiraDataCollector, name: str):
        """
        Constructor.
        :param name: Page name
        """

        super().__init__(mira.config)
        self.vncclient = mira.vncclient
        self.config = mira.config
        self.name = name

        if "DEBUG_OUTPUT" in os.environ and os.environ["DEBUG_OUTPUT"] == "1":
            self.DEBUG_OUTPUT = True

        if "DEBUG_IMAGE_WRITING" in os.environ and os.environ["DEBUG_IMAGE_WRITING"] == "1":
            self.DEBUG_IMAGE_WRITING = True
    # end __init__()

    def take_screenshot(self) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshot_path = self.name + f"screenshot_{timestamp}.png"
        self.vncclient.refreshScreen()
        self.vncclient.captureScreen(self.screenshot_path)
        if self.DEBUG_OUTPUT:
            print(f"Screenshot stored: {self.screenshot_path}")
    # end take_screenshot()

    def delete_screenshot(self) -> None:
        if self.screenshot_path is None:
            if self.DEBUG_OUTPUT:
                print("No screenshot to be deleted.")
        else:
            if (not 'DebugKeepScreenshots' in self.config
                    or not self.config['DebugKeepScreenshots']):
                try:
                    os.remove(self.screenshot_path)
                except FileNotFoundError:
                    print(f"File '{self.screenshot_path}' could not be deleted.")
    # end delete_screenshot()

    def check_mandatory_content(self, mandatory_text: list[str]) -> bool:
        # Check, if mandatory text can be found in page
        # Abort, if not present
        if mandatory_text is not None:
            if self.DEBUG_OUTPUT:
                print ("Checking for mandatory texts: %s" % ('+'.join(mandatory_text)))
            image = Image.open(self.screenshot_path)
            text = pytesseract.image_to_string(image, self.config['OCRLanguage'])

            for t in mandatory_text:
                if t not in text:
                    print("%s not found in page %s" % (t, self.name))
                    if self.DEBUG_OUTPUT:
                        print (f"Raw page text content: '{text}'")
                    return False
        return True
    # end check_mandatory_content()

    def do_mouse_moves_and_click(self, move_definition: list) -> bool:
        for m in move_definition:
            # Move mouse to coordinates and click
            self.vncclient.mouseMove(m['moveTo'][0],
                                     m['moveTo'][1])
            time.sleep(0.2)
            self.vncclient.mousePress(1)
            time.sleep(2)

            if 'MandatoryText' not in m or m['MandatoryText'] is None:
                return True

            # Check if mandatory text exists
            self.take_screenshot()

            mandatory_found = self.check_mandatory_content(m['MandatoryText'])

            # Delete screenshot
            self.delete_screenshot()

            if not mandatory_found:
                return False
        return True
    # end do_mouse_moves_and_click()

    def process_regions(self) -> None:
        page_config = self.config['Pages'][self.name]

        # Load image with OpenCV and then Pillow
        img = cv2.imread(self.screenshot_path)
        image = Image.fromarray(img)

        # Loop over all regions of current page
        regions = page_config['Regions']
        for key, region_config in regions.items():
            if self.DEBUG_OUTPUT:
                print("Processing region %s..." % key)

            secondarykey = None
            if 'secondaryKey' in region_config.keys():
                secondarykey = region_config['secondaryKey']

            decpt = region_config['decpt'] if 'decpt' in region_config else None

            region: MiraRegion = MiraRegion(key,
                                            secondarykey,
                                            image,
                                            region_config['coordinates'],
                                            region_config['preProcessing'],
                                            region_config['ocrConfig'],
                                            self.config['OCRLanguage'],
                                            self.config['locale'],
                                            decpt)

            if ('DebugDeleteImageAfterSuccess' in self.config
                and self.config['DebugDeleteImageAfterSuccess']):
                region.set_debug_delete_image_after_success(True)

            self.data.update(region.process_numeric_values())