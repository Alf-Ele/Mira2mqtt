"""
Connect to an Ovum heatpump via VNC and extract data from the Mira user interface.

Check here for more details:
https://github.com/Schneydr/Mira2mqtt

@author Schneydr
@date 2025/11/11
"""

import datetime
import locale
import glob
import os
import re
import cv2
import numpy as np
import pytesseract
import json

class MiraRegion:
    """
    A region in the Mira user interface used for retrieving values via OCR.
    """

    DEBUG_OUTPUT = False
    DEBUG_IMAGE_WRITING = False

    key: str = None
    img: cv2 = None
    language = None
    ui_locale = None
    real_decpt = None
    real_thpt = None
    decpt = None
    img_prefix = None
    regionConfig = None

    DebugDeleteImageAfterSuccess = False

    def __init__(self,
                 key: str,
                 region_config: dict,
                 img: 'cv2',
                 language: str,
                 ui_locale: str):
        """
        Constructor of a MiraRegion.
        :param key: Region key (unique identifier)
        :param region_config: Region confg
        :param img: Mira UI screenshot
        :param language: OCR language
        :param ui_locale: Locale for numbers shown in UI
        """

        if "DEBUG_OUTPUT" in os.environ and os.environ["DEBUG_OUTPUT"] == "1":
            self.DEBUG_OUTPUT = True

        if "DEBUG_IMAGE_WRITING" in os.environ and os.environ["DEBUG_IMAGE_WRITING"] == "1":
            self.DEBUG_IMAGE_WRITING = True

        # Crop and grey scale image from given coordinates
        self.key = key
        self.regionConfig = region_config
        self.img = cv2.cvtColor(np.array(img.crop(region_config['coordinates'])),
                                cv2.COLOR_BGR2GRAY)
        self.language = language
        self.ui_locale = ui_locale
        self.decpt = region_config['decpt'] if 'decpt' in region_config else None

        #cv2.imwrite("processed-" + pp + "-" + self.key + ".png", self.img)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self.img_prefix = f'processed-{key}-{timestamp}-'

        # Set correct decimal point and thousands separators in case of parsing errors
        self.set_numeric_separators()

    def set_debug_delete_image_after_success(self, flag: bool) -> None:
        self.DebugDeleteImageAfterSuccess = flag

    def enhance_contrast(self) -> None:
        """
        Pre-processing of image: Enhance contrast.
        :return:
        """

        # call addWeighted function. use beta = 0 to effectively only operate on one image
        #                                   contrast           brightness
        self.img = cv2.addWeighted(self.img, 3, self.img, 0, 0)

    def adaptive_thresholding(self) -> None:
        """
        Pre-processing of image: Adaptive Thresholding (better for changing backgrounds).
        """

        self.img = cv2.adaptiveThreshold(
            self.img, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C,  # ADAPTIVE_THRESH_MEAN_C or ADAPTIVE_THRESH_GAUSSIAN_C
            cv2.THRESH_BINARY,
            11, 2
            # 11, 2
        )

    def invert(self) -> None:
        """
        Pre-processing of image: Invert the image. Use if the text is bright.
        """

        self.img = cv2.bitwise_not(self.img)

    def image_smoothen(self) -> None:
        """
        Pre-processing of image: Smooth the image for improving accuracy of OCR.
        Based on code by Trenton McKinney:
        https://trenton3983.github.io/posts/ocr-image-processing-pytesseract-cv2/
        """

        # Step 1: Apply binary thresholding to the input image
        ret1, th1 = cv2.threshold(self.img, 88, 255, cv2.THRESH_BINARY)

        # Step 2: Apply Otsu's thresholding to further enhance the binary image
        ret2, th2 = cv2.threshold(th1, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Step 3: Perform Gaussian blurring to reduce noise
        blur = cv2.GaussianBlur(th2, (5, 5), 0)

        # Step 4: Apply another Otsu's thresholding to obtain the final smoothed image
        ret3, th3 = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        self.img = th3
        return
    # end image_smoothen()

    def remove_noise_and_smooth(self) -> None:
        """
        Pre-processing of image: Remove noise from and smooth an OpenCV image.
        Based on code by Trenton McKinney:
        https://trenton3983.github.io/posts/ocr-image-processing-pytesseract-cv2/
        """

        # Apply adaptive thresholding to filter out noise and enhance text visibility
        filtered = cv2.adaptiveThreshold(self.img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 41)

        # Define a kernel for morphological operations (erosion and dilation)
        kernel = np.ones((1, 1), np.uint8)

        # Perform morphological opening to remove small noise regions
        opening = cv2.morphologyEx(filtered, cv2.MORPH_OPEN, kernel)

        # Perform morphological closing to fill gaps in text regions
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)

        # Further smoothen the image using a custom function (image_smoothen)
        self.image_smoothen()

        # Combine the smoothened image with the closing result using bitwise OR
        self.img = cv2.bitwise_or(self.img, closing)

        return
    # end remove_noise_and_smooth()

    def write_file(self, file_name: str) -> None:
        """
        Writes the region image to a file. Useful for debugging
        :param file_name: Image file name
        """
        cv2.imwrite(file_name, self.img)

    def retrieve_text(self) -> str:
        """
        Retrieve text from region image.
        :return: retrieved text
        """
        ocr_language = self.regionConfig['ocrLanguage'] if 'ocrLanguage' in self.regionConfig else self.language

        return pytesseract.image_to_string(self.img,
                                           lang=ocr_language,
                                           config=self.regionConfig['ocrConfig'])

    def process_and_retrieve(self) -> str:
        """
        Pre-processes and then retrieves text from a Mira UI region.
        :return: Retrieved text
        """
        pre_processing = self.regionConfig['preProcessing']

        # grayscale the image
        if self.DEBUG_IMAGE_WRITING:
            cv2.imwrite(f"{self.img_prefix}gray.png", self.img)

        if self.DEBUG_OUTPUT:
            print (f"Pre-processing region {self.key} image for: {pre_processing}...")
        for pp in pre_processing.split("+"):
            if pp == "contrast":
                self.enhance_contrast()
            elif pp == "denoise":
                self.remove_noise_and_smooth()
            elif pp == "smooth":
                self.image_smoothen()
            if pp == "thresh":
                self.adaptive_thresholding()
            if pp == "invert":
                self.invert()

            # For debugging write processed image to file and print out retrived text
            if self.DEBUG_IMAGE_WRITING:
                cv2.imwrite(f"{self.img_prefix}{pp}.png", self.img)
            if self.DEBUG_OUTPUT:
                print ("... retrieved text after %s pre-processing: '%s'" % (pp, self.retrieve_text().strip()))

        return self.retrieve_text().strip()
    # end process_and_retrieve()

    def set_numeric_separators(self) -> None:
        """
            Sets the locale and returns the decimal point character.
        """
        try:
            # Set the locale for numeric formatting
            locale.setlocale(locale.LC_NUMERIC, self.ui_locale)

            # Get the locale conventions
            settings = locale.localeconv()

            # Extract the decimal point character
            self.real_decpt = settings['decimal_point']
            self.real_thpt = settings['thousands_sep']

            #if self.DEBUG_OUTPUT:
            #    print(f"... decimal point = {self.real_decpt} - thousands seperator = {self.real_thpt}")

        except locale.Error as e:
            print(f"Error setting locale to {self.ui_locale}: {e}")
            return None
        finally:
            # reset the locale
            locale.setlocale(locale.LC_NUMERIC, locale.getdefaultlocale())
            pass
    # end set_numeric_separators()

    def clean_numeric_separators(self, value: str) -> str:
        ret_value = value

        if self.decpt is not None:
            # Change decimal point
            ret_value = value.replace(self.decpt, self.real_decpt)

        # Remove thousands separator
        ret_value = ret_value.replace(self.real_thpt, '')

        return ret_value

    def get_numeric_value(self, strvalue: str) -> float:
        # Set locale for parsing localized values
        locale.setlocale(locale.LC_ALL, self.ui_locale)

        numvalue: float

        try:
            numvalue = locale.atof(strvalue)
        except ValueError:
            print(f"... ERROR: could not get numeric value for {strvalue}")
            numvalue: float = 0.0
        finally:
            # reset the locale
            locale.setlocale(locale.LC_NUMERIC, locale.getdefaultlocale())

        return numvalue
    # end get_only_numeric_value()

    def clean_num_value(self, key: str, value: str) -> str:
        # Cleanup and parse numeric data before publishing
        strvalue = self.clean_numeric_separators(value.strip())
        numvalue = None
        if str(strvalue).endswith("kWh"):
            strvalue = str(strvalue).removesuffix("kWh")
            numvalue = self.get_numeric_value(strvalue)
        elif str(strvalue).endswith("MWh"):
            strvalue = str(strvalue).removesuffix("MWh")
            numvalue = self.get_numeric_value(strvalue)
            numvalue *= 1000
        elif str(strvalue).endswith("kW"):
            strvalue = str(strvalue).removesuffix("kW")
            numvalue = self.get_numeric_value(strvalue)
            numvalue *= 1000
        elif str(strvalue).endswith("W"):
            strvalue = str(strvalue).removesuffix("W")
            numvalue = self.get_numeric_value(strvalue)
        elif str(strvalue).endswith("°C"):
            strvalue = str(strvalue).removesuffix("°C")
            numvalue = self.get_numeric_value(strvalue)

        if numvalue is not None:
            if 'maxValue' in self.regionConfig:
                while numvalue > self.regionConfig['maxValue']:
                    numvalue /= 10

            if 'mandatoryDecimalPlaces' in self.regionConfig:
                decimals = strvalue.split(self.real_decpt)

                # We don't have decimals after the dot
                if len(decimals) <= 1:
                    print('... number needed decimal fixing')
                    numvalue /= pow(10, self.regionConfig['mandatoryDecimalPlaces'])

            strvalue = str(numvalue)

            if self.DEBUG_OUTPUT:
                print(f"... cleaned numeric value for {key} = '{strvalue}'")
        else:
            if self.DEBUG_OUTPUT:
                print(f"... cleaned string value for {key}  = '{strvalue}'")

        return strvalue
    # end clean_num_value()

    def process_numeric_values(self) -> dict:
        # Return data set
        data = {}

        # Do we have a secondary key?
        if 'secondaryKey' in self.regionConfig:
            secondary_key = self.regionConfig['secondaryKey']
        else:
            secondary_key = None

        # Retrieve text from region
        text = self.process_and_retrieve()
        if MiraRegion.DEBUG_OUTPUT:
            print("Detected text in region %s: '%s'" % (self.key, text))

        # Split text if we've got a secondary value in brackets
        if "(" in text:
            texts = text.split("(")
        else:
            texts = [text]

        # Process the text parts
        i=0
        for current_text in texts:
            # Get key for current value
            current_key = self.key
            if i > 0:
                if secondary_key is None:
                    continue
                current_key = secondary_key

            # Get unit of current value - if present
            defined_unit = None
            if 'unit' in self.regionConfig:
                if isinstance(self.regionConfig['unit'], list):
                    defined_unit = self.regionConfig['unit'][i]
                else:
                    defined_unit = self.regionConfig['unit']

            if self.DEBUG_OUTPUT:
                if len(text) > 1:
                    print(f"... retrieved text after splitting: '{current_text}'")

            # Check for mandatory text entries:
            if 'MandatoryText' in self.regionConfig:
                mandatory_texts = []
                if isinstance(self.regionConfig['MandatoryText'], list):
                    mandatory_texts = self.regionConfig['MandatoryText']
                else:
                    mandatory_texts.append(self.regionConfig['MandatoryText'])

                for t in mandatory_texts:
                    if t not in current_text:
                        print(f"... {t} not found for {current_key}")
                        current_text = ''

            # Strip text from leading and trailing spaces
            current_text = current_text.strip()

            # Workaround for zero values
            if current_text.upper() == '0WW' or current_text.upper() == '0W':
                current_text = '0W'

            # Workaround for wrongly recognized numbers
            corrected_text = current_text.replace("A","4")
            corrected_text = corrected_text.replace("B", "8")
            corrected_text = corrected_text.replace("D","0")
            corrected_text = corrected_text.replace("I","1")
            corrected_text = corrected_text.replace("T", "7")
            corrected_text = corrected_text.replace("ı", " ")

            # Extract values (temperature or power)
            match_temp = re.search(r"(-?\d{1,2},?\d)\s*°C", corrected_text)
            match_energy = re.search(r"(-?\d+[.,]?\d*)\s*(kWh|kwh|Kwh|KWh|mwh|Mwh|MWh)", corrected_text)
            match_power = re.search(r"(-?\d+[.,]?\d*)\s*(w|W|kW|kw|KW|kkW|kKW)", corrected_text)

            if match_temp:
                value = self.clean_num_value(current_key, match_temp.group(1) + "°C")
                data[current_key] = value
                print(f"... Detected temperature: {value}")
            elif match_energy:
                # Correct uper/lower case errors in unit
                unit = (match_energy.group(2)).replace("w", "W")
                unit = unit.replace("H", "h")
                unit = unit.replace("KW", "kW")
                unit = unit.replace("mW", "MW")

                # Get corrected numeric value
                value = self.clean_num_value(current_key, match_energy.group(1) + unit)

                data[current_key] = value

                print(f"... Detected energy: {value}")
            elif match_power:
                # Correct uper/lower case errors in unit
                unit = (match_power.group(2)).replace("w", "W")
                unit = unit.replace("KW", "kW")
                unit = unit.replace("kw", "kW")
                unit = unit.replace("kKW", "kW")

                # Get corrected numeric value
                value = self.clean_num_value(current_key, match_power.group(1) + unit)

                data[current_key] = value

                print(f"... Detected power: {value}")
            else:
                if self.DEBUG_OUTPUT:
                    print(f"... retrieved text: '{current_text}'")

                if defined_unit is not None and defined_unit != 'None':
                    data[current_key] = ''
                    print(f"... Skipping text value '{current_text}' for value of unit {defined_unit}!")
                else:
                    #data[current_key] = "N/A"
                    data[current_key] = current_text
                    print(f"... Detected text: {current_text}")

            i += 1

        if self.DebugDeleteImageAfterSuccess:
            if self.key in data or secondary_key in data:
                for f in glob.glob(f"{self.img_prefix}*.png"):
                    try:
                        os.remove(f)
                    except FileNotFoundError:
                        print(f"File '{f}' could not be deleted.")

        return data
    # end processNumericValues()

    def get_auto_discovery_data(self) -> list:
        data = []
        keys = [self.key]

        # Do we have a secondary key?
        if 'secondaryKey' in self.regionConfig:
            keys.append(self.regionConfig['secondaryKey'])

        i=0
        for k in keys:
            # Get defaults
            if 'deviceClass' in self.regionConfig:
                if isinstance(self.regionConfig['deviceClass'], list):
                    device_class = self.regionConfig['deviceClass'][i]
                else:
                    device_class = self.regionConfig['deviceClass']
            else:
                device_class = 'None'

            if 'stateClass' in self.regionConfig:
                if isinstance(self.regionConfig['stateClass'], list):
                    state_class = self.regionConfig['stateClass'][i]
                else:
                    state_class = self.regionConfig['stateClass']
            else:
                state_class = 'measurement'

            if 'unit' in self.regionConfig:
                if isinstance(self.regionConfig['unit'], list):
                    unit = self.regionConfig['unit'][i]
                else:
                    unit = self.regionConfig['unit']
            else:
                unit = 'None'

            if 'valueTemplate' in self.regionConfig:
                if isinstance(self.regionConfig['valueTemplate'], list):
                    value_template = self.regionConfig['valueTemplate'][i]
                else:
                    value_template = self.regionConfig['valueTemplate']
            else:
                value_template = 'None'

            data.append({'uniq_id': k,
                         'name': k,
                         'dev_cla': device_class,
                         'state_class': state_class,
                         'unit_of_meas': unit,
                         'val_tpl': value_template}
                        )

            # Increment counter
            i += 1

        return data
    # end get_auto_discovery_data()
