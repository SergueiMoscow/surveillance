#!/bin/bash

# Проверка установки poetry
POETRY_CHECK="$(which poetry)"
if [ "$POETRY_CHECK" == "" ]; then
    curl -sSL https://install.python-poetry.org | bash
else
    echo "poetry already installed"
fi

# Создание виртуальной среды
poetry config virtualenvs.create true --local

# Установка зависимостей
poetry install