"""
Connect to an Ovum heatpump via VNC and extract data from the Mira user interface.

Check here for more details:
https://github.com/Schneydr/Mira2mqtt

@author Schneydr
@date 2025/11/11
"""

import locale
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
    decpt = None

    def __init__(self,
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
        # Crop and grey scale image from given coordinates
        self.key = key
        self.secondaryKey = secondarykey
        self.img = cv2.cvtColor(np.array(img.crop(coordinates)), cv2.COLOR_BGR2GRAY)
        self.preProcessing = preprocessing
        self.ocrConfig = ocrconfig
        self.language = language
        self.numlocale = numlocale
        self.decpt = decpt

        # Get correct decimal point in case of parsing errors
        self.real_decpt = self.get_decimal_separator()

        if "DEBUG_OUTPUT" in os.environ and os.environ["DEBUG_OUTPUT"] == "1":
            self.DEBUG_OUTPUT = True

        if "DEBUG_IMAGE_WRITING" in os.environ and os.environ["DEBUG_IMAGE_WRITING"] == "1":
            self.DEBUG_IMAGE_WRITING = True

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
        #if "gray" in self.preProcessing: # grayscaling is done automatically
        cv2.imwrite("processed-gray-" + self.key +  ".png", self.img)

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
                cv2.imwrite("processed-" + pp + "-" + self.key + ".png", self.img)
            if self.DEBUG_OUTPUT:
                print ("... retrieved text after %s pre-processing: '%s'" % (pp, self.retrieve_text().strip()))

        return self.retrieve_text().strip()
    # end process_and_retrieve()

    def get_decimal_separator(self) -> chr:
        """
            Sets the locale and returns the decimal point character.
        """
        try:
            # Set the locale for numeric formatting
            locale.setlocale(locale.LC_NUMERIC, self.numlocale)

            # Get the locale conventions
            settings = locale.localeconv()

            # Extract the decimal point character
            decimal_char = settings['decimal_point']

            return decimal_char

        except locale.Error as e:
            print(f"Error setting locale to {self.numlocale}: {e}")
            return None
        finally:
            # reset the locale
            locale.setlocale(locale.LC_NUMERIC, locale.getdefaultlocale())
            pass
    # end get_decimal_separator()

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

            # Extract values (temperature or power)
            match_temp = re.search(r"(\d{1,2},\d)\s*°C", current_text)
            match_energy = re.search(r"(\d+[.,]?\d*)\s*(kWh|kwh|Kwh|KWh|mwh|Mwh|MWh)", current_text)
            match_power = re.search(r"(\d+[.,]?\d*)\s*(kW|W|kw|KW)", current_text)

            if match_temp:
                # Fix wrong decimal point
                if self.decpt is not None:
                    value = match_temp.group(1).replace(self.decpt, self.real_decpt)
                else:
                    value = match_temp.group(1)
                data[current_key] = value + " °C"
            elif match_energy:
                # Fix wrong decimal point
                if self.decpt is not None:
                    value = match_energy.group(1).replace(self.decpt, self.real_decpt)
                else:
                    value = match_energy.group(1)
                # Correct uper/lower case errors in unit
                unit = (match_energy.group(2)).replace("w", "W")
                unit = unit.replace("KW", "kW")
                unit = unit.replace("kw", "kW")
                unit = unit.replace("mw", "MW")
                unit = unit.replace("Mw", "MW")
                data[current_key] = value + " " + unit
            elif match_power:
                # Fix wrong decimal point
                if self.decpt is not None:
                    value = match_power.group(1).replace(self.decpt, self.real_decpt)
                else:
                    value = match_power.group(1)
                # Correct uper/lower case errors in unit
                unit = (match_power.group(2)).replace("w", "W")
                unit = unit.replace("KW", "kW")
                unit = unit.replace("kw", "kW")
                data[current_key] = value + " " + unit
            else:
                data[current_key] = "N/A"

            i += 1

        return data
    # end processNumericValues()