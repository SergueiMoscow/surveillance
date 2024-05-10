#!/bin/bash

# Проверка и установка python3-venv если необходимо
sudo apt-get install python3-venv -y

# Создание виртуальной среды
python3 -m venv venv

# Активация виртуальной среды и установка пакетов
source ./venv/bin/activate
pip install -r requirements.txt
deactivate