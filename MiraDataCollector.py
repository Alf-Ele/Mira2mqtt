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
import tempfile
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
    auto_discovery: list = None

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
        self.data = {'Timestamp': self.timestamp}
        self.auto_discovery: list = []
        #self.config['autoDiscoveryTemplate']['stat_t'] = self.config['mqttStatusTopic']

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
        # Disconect from VNC
        if self.vncclient is not None:
            self.vnc_disconnect()

        # Disconnect from MQTT broker
        self.mqtt_client.disconnect()
        self.mqtt_client.loop_stop()
    # end __exit__()

    def connect_mqtt(self) -> None:
        if 'mqttUsage' in self.config and not self.config['mqttUsage']:
            return

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

    def mqtt_publish(self, topic: str, message: str, retain: bool = False):
        if 'mqttUsage' in self.config and not self.config['mqttUsage']:
            return

        # Publish message
        if retain:
            msg_info = self.mqtt_client.publish(topic, message, qos=1, retain=True)
        else:
            msg_info = self.mqtt_client.publish(topic, message, qos=1)
        self.unacked_publish.add(msg_info.mid)
        msg_info.wait_for_publish()
    # end mqtt_publish()

    def publish_data(self):
        # Set locale for parsing localized values
        locale.setlocale(locale.LC_ALL, self.config['locale'])

        # Publish auto discovery message
        if self.config['mqttAutoDiscovery']:
            if self.DEBUG_OUTPUT:
                print("Number of auto discovery messages: %i" % len(self.auto_discovery))
            for i in range(len(self.auto_discovery)):
                if self.DEBUG_OUTPUT:
                    print("-------- AUTO DISCOVERY COMPONENT --------")
                    print(json.dumps(self.auto_discovery[i]))

                topic: str = self.config['mqttAutoDiscoveryTopic']
                name: str = self.auto_discovery[i]['name']
                topic = topic.replace('%s', name)
                if self.DEBUG_OUTPUT:
                    print(f"Setting sensor name '{name}' to topic name -> '{topic}'")

                # Publish auto discover message
                self.mqtt_publish(topic,
                                  json.dumps(self.auto_discovery[i]),
                                  True)
            if self.DEBUG_OUTPUT:
                print("------------------------------------------")

        # Publish data
        self.mqtt_publish(self.config['mqttStatusTopic'],
                          json.dumps(self.data))
        if self.DEBUG_OUTPUT:
            print(f"State messages published to {self.config['mqttStatusTopic']}")
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

        mira_pages=[]

        # Traverse all pages and make screenshots
        for page, page_config in self.config['Pages'].items():
            print("Processing page %s..." % page)
            mira_page = MiraPage(self, page)

            if page_config['MouseMovesAndClicks'] is not None:
                mandatory_found = mira_page.do_mouse_moves_and_click(page_config['MouseMovesAndClicks'])
                if not mandatory_found:
                    continue

            mira_page.take_screenshot()
            mira_pages.append(mira_page)

        # Travers all pages a second time to process their regions
        for mira_page in mira_pages:
            mira_page.process_regions()
            self.data.update(mira_page.data)

            # Assemble auto discovery messages
            for ad_message in mira_page.auto_discovery:
                self.auto_discovery.append(ad_message)

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

    DEBUG_OUTPUT = True
    DEBUG_IMAGE_WRITING = True

    name: str = None
    pil_image = None
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
        self.auto_discovery = []

        if "DEBUG_OUTPUT" in os.environ and os.environ["DEBUG_OUTPUT"] == "1":
            self.DEBUG_OUTPUT = True

        if "DEBUG_IMAGE_WRITING" in os.environ and os.environ["DEBUG_IMAGE_WRITING"] == "1":
            self.DEBUG_IMAGE_WRITING = True
    # end __init__()

    def take_screenshot(self) -> None:
        self.vncclient.refreshScreen()

        # Capture screen to memory
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_filename = temp_file.name
        temp_file.close()
        try:
            self.vncclient.captureScreen(temp_filename)
            self.pil_image = Image.open(temp_filename)

            if 'DebugKeepScreenshots' in self.config and self.config['DebugKeepScreenshots']:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                self.screenshot_path = self.name + f"screenshot_{timestamp}.png"
                self.pil_image.save(self.screenshot_path, "PNG")

                if self.DEBUG_OUTPUT:
                    print(f"Screenshot stored: {self.screenshot_path}")

        except Exception as e:
            print(f"An error ocurred: {e}")
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
    # end take_screenshot()

    def check_mandatory_content(self, mandatory_text: list[str]) -> bool:
        # Check, if mandatory text can be found in page
        # Abort, if not present
        if mandatory_text is not None:
            if self.DEBUG_OUTPUT:
                print ("Checking for mandatory texts: %s" % ('+'.join(mandatory_text)))
            #image = Image.open(self.screenshot_path)
            #text = pytesseract.image_to_string(image, self.config['OCRLanguage'])
            text = pytesseract.image_to_string(self.pil_image, self.config['OCRLanguage'])

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
            time.sleep(0.5)
            self.vncclient.mousePress(1)
            time.sleep(0.5)

            self.take_screenshot()

            if 'MandatoryText' not in m or m['MandatoryText'] is None:
                return True

            # Check if mandatory text exists
            mandatory_found = self.check_mandatory_content(m['MandatoryText'])

            if not mandatory_found:
                print("Mandatory text [%s] not found in page!" % m['MandatoryText'] )
                return False
        return True
    # end do_mouse_moves_and_click()

    def process_regions(self) -> None:
        page_config = self.config['Pages'][self.name]

        # Load image with OpenCV and then Pillow
        #img = cv2.imread(self.screenshot_path)
        #image = Image.fromarray(img)
        # Load image from class instance
        image = self.pil_image

        # Loop over all regions of current page
        regions = page_config['Regions']
        for key, region_config in regions.items():
            if self.DEBUG_OUTPUT:
                print("Processing region %s..." % key)

            region: MiraRegion = MiraRegion(key,
                                            region_config,
                                            image,
                                            self.config['OCRLanguage'],
                                            self.config['locale'])

            if ('DebugDeleteImageAfterSuccess' in self.config
                and self.config['DebugDeleteImageAfterSuccess']):
                region.set_debug_delete_image_after_success(True)

            self.data.update(region.process_numeric_values())

            # Append auto discovery message for every key in curent region
            if self.config['mqttAutoDiscovery']:
                for dm_part in region.get_auto_discovery_data():
                    discovery_message: dict = self.config['autoDiscoveryTemplate'].copy()
                    # Add device id to sensor unique id
                    dm_part['uniq_id'] = discovery_message['device']['ids'][0] + '-' + dm_part['uniq_id']
                    # Now add the discovery message part to get the final message
                    #discovery_message.update(dm_part)
                    discovery_message['name'] = dm_part['name']
                    discovery_message['uniq_id'] = dm_part['uniq_id']
                    discovery_message['dev_cla'] = dm_part['dev_cla']
                    discovery_message['state_class'] = dm_part['state_class']
                    discovery_message['unit_of_meas'] = dm_part['unit_of_meas']
                    discovery_message['val_tpl'] = dm_part['val_tpl']

                    self.auto_discovery.append(discovery_message)
