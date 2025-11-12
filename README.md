# Mira2mqtt
Monitor Ovum heatpumps with Mira firmware via VNC.

Currently Ovum doesn not provide an official API to connect to their heat pumps running the new Mira firmware.
This software attempts to circumvent this by connecting to the VNC port provided by Mira and retrieving data via OCR (optical character recognition).
The retrieved data is then sent to a MQTT broker, where it can be further processed, e.g., by a home automation solution such as OpenHAB, Home Assistant, and others.

## Installation
### Install required packages (Debian or Ubuntu)
```
sudo apt update
sudo apt install python3 python3-venv python3-pip tesseract-ocr ffmpeg libsm6 libxext6 git
```

### Aditionally install OCR language package
You must install a special language pack for the language in which your Mira user interface is currently configured (not required for English).
Example for German:
```
apt install tesseract-ocr-deu
```

### Clone the Github repository
```
git clone https://github.com/Schneydr/Mira2mqtt.git
```

### Create and use python environment
```
cd Mira2mqtt
mkdir -p .venv
python3 -m venv .venv
. .venv/bin/activate

### Install python packages
python3 -m pip install --upgrade pip 
python3 -m pip install opencv-python
python3 -m pip install vncdotool
python3 -m pip install pytesseract
python3 -m pip install paho-mqtt
```

### Configure 
You need to set at least the hostname or ip address of your heat pump within your local network. Furthermore, you shoud configure the language and locale matching the setting of your Mira UI.
In case you want to use MQTT you have to activate MQTT and configure broker ip address, port, user and password.
```
nano mira2mqtt.py
```

### Run the programm
```
./mira.sh
```
