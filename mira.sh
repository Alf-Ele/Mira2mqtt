#!/usr/bin/env bash

path=$(dirname $0)
. ${path}/.venv/bin/activate
python3 ${path}/mira2mqtt.py
