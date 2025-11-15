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

class MiraRegion:
    """
    A region in the Mira user interface used for retrieving values via OCR.
    """

    DEBUG_OUTPUT = False
    DEBUG_IMAGE_WRITING = False

    key: str = None
    secondaryKey: str = None
    img: cv2 = None
    preProcessing: str = None
    ocrConfig = None
    language = None
    numlocale = None
    real_decpt = None
    real_thpt = None
    decpt = None
    img_prefix = None
    regionConfig = None

    DebugDeleteImageAfterSuccess = False

    def __init__(self,
                 region_config: dict,
                 key: str,
                 secondarykey: str,
                 img: 'cv2',
                 coordinates: tuple[int, int, int, int],
                 preprocessing: str,
                 ocrconfig: str,
                 language: str,
                 numlocale: str,
                 decpt: str):
        """
        Constructor of a MiraRegion.
        :param key: Region key (unique identifier)
        :param secondarykey: Optional secondary key for further value in brackets
        :param img: Mira UI screenshot
        :param coordinates: Region coordinates
        :param preprocessing: type of pre-processing needed for OCR
        :param ocrconfig: tesseract configuration (OCR)
        :param language: OCR language
        """

        if "DEBUG_OUTPUT" in os.environ and os.environ["DEBUG_OUTPUT"] == "1":
            self.DEBUG_OUTPUT = True

        if "DEBUG_IMAGE_WRITING" in os.environ and os.environ["DEBUG_IMAGE_WRITING"] == "1":
            self.DEBUG_IMAGE_WRITING = True

        # Crop and grey scale image from given coordinates
        self.regionConfig = region_config
        self.key = key
        self.secondaryKey = secondarykey
        self.img = cv2.cvtColor(np.array(img.crop(coordinates)), cv2.COLOR_BGR2GRAY)
        self.preProcessing = preprocessing
        self.ocrConfig = ocrconfig
        self.language = language
        self.numlocale = numlocale
        self.decpt = decpt

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
        return pytesseract.image_to_string(self.img,
                                           lang=self.language,
                                           config=self.ocrConfig)

    def process_and_retrieve(self) -> str:

        """
        Pre-processes and then retrieves text from a Mira UI region.
        :return: Retrieved text
        """
        # grayscale the image
        if self.DEBUG_IMAGE_WRITING:
            cv2.imwrite(f"{self.img_prefix}gray.png", self.img)

        if self.DEBUG_OUTPUT:
            print (f"Pre-processing region {self.key} image for: {self.preProcessing}...")
        for pp in self.preProcessing.split("+"):
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
            locale.setlocale(locale.LC_NUMERIC, self.numlocale)

            # Get the locale conventions
            settings = locale.localeconv()

            # Extract the decimal point character
            self.real_decpt = settings['decimal_point']
            self.real_thpt = settings['thousands_sep']

            #if self.DEBUG_OUTPUT:
            #    print(f"... decimal point = {self.real_decpt} - thousands seperator = {self.real_thpt}")

        except locale.Error as e:
            print(f"Error setting locale to {self.numlocale}: {e}")
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

        if self.DEBUG_OUTPUT:
            print(f"... value after numeric separators cleansing:'{value}' ->  {ret_value}")

        return ret_value

    def clean_num_value(self, key: str, value: str) -> str:
        # Set locale for parsing localized values
        locale.setlocale(locale.LC_ALL, self.numlocale)

        # Cleanup and parse numeric data before publishing
        strvalue = value
        numvalue = None
        if str(value).endswith("kWh"):
            strvalue = str(value).removesuffix("kWh")
            strvalue = self.clean_numeric_separators(strvalue)
            numvalue = locale.atof(strvalue)
        elif str(value).endswith("MWh"):
            strvalue = str(value).removesuffix("MWh")
            strvalue = self.clean_numeric_separators(strvalue)
            numvalue = locale.atof(strvalue)
            numvalue *= 1000
        elif str(value).endswith("kW"):
            strvalue = str(value).removesuffix("kW")
            strvalue = self.clean_numeric_separators(strvalue)
            numvalue = locale.atof(strvalue)
            numvalue *= 1000
        elif str(value).endswith("W"):
            strvalue = str(value).removesuffix("W")
            strvalue = self.clean_numeric_separators(strvalue)
            numvalue = locale.atof(strvalue)
        elif str(value).endswith("°C"):
            strvalue = str(value).removesuffix("°C")
            strvalue = self.clean_numeric_separators(strvalue)
            numvalue = locale.atof(strvalue)

        # reset the locale
        locale.setlocale(locale.LC_NUMERIC, locale.getdefaultlocale())

        if numvalue is not None:
            if 'maxValue' in self.regionConfig:
                while numvalue > self.regionConfig['maxValue']:
                    numvalue /= 10
            strvalue = str(numvalue)

        if self.DEBUG_OUTPUT:
            print(f"... cleaned value for {key} = '{strvalue}'")

        return strvalue
    # end clean_num_value()

    def process_numeric_values(self) -> dict:
        # Return data set
        data = {}

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
            current_key = self.key
            if i > 0:
                if self.secondaryKey is not None:
                    current_key = self.secondaryKey
                else:
                    continue

            if self.DEBUG_OUTPUT:
                if len(text) > 1:
                    print(f"... retrieved text after splitting: '{current_text}'")

            # Strip text from leading and trailing spaces
            current_text = current_text.strip()

            # Extract values (temperature or power)
            match_temp = re.search(r"(\d{1,2},?\d)\s*°C", current_text)
            match_energy = re.search(r"(\d+[.,]?\d*)\s*(kWh|kwh|Kwh|KWh|mwh|Mwh|MWh)", current_text)
            match_power = re.search(r"(\d+[.,]?\d*)\s*(kW|W|kw|KW|kKW)", current_text)

            if match_temp:
                value = self.clean_num_value(current_key, match_temp.group(1) + "°C")
                data[current_key] = value
            elif match_energy:
                # Correct uper/lower case errors in unit
                unit = (match_energy.group(2)).replace("w", "W")
                unit = unit.replace("KW", "kW")
                unit = unit.replace("kw", "kW")
                unit = unit.replace("mw", "MW")
                unit = unit.replace("Mw", "MW")

                # Get corrected numeric value
                value = self.clean_num_value(current_key, match_energy.group(1) + unit)

                data[current_key] = value
            elif match_power:
                # Correct uper/lower case errors in unit
                unit = (match_power.group(2)).replace("w", "W")
                unit = unit.replace("KW", "kW")
                unit = unit.replace("kw", "kW")
                unit = unit.replace("kKW", "kW")

                # Get corrected numeric value
                value = self.clean_num_value(current_key, match_power.group(1) + unit)

                data[current_key] = value
            else:
                if self.DEBUG_OUTPUT:
                    print(f"... retrieved text: '{current_text}'")
                #data[current_key] = "N/A"
                data[current_key] = current_text

            i += 1

        if self.DebugDeleteImageAfterSuccess:
            if self.key in data or self.secondaryKey in data:
                for f in glob.glob(f"{self.img_prefix}*.png"):
                    try:
                        os.remove(f)
                    except FileNotFoundError:
                        print(f"File '{f}' could not be deleted.")

        return data
    # end processNumericValues()