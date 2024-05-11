FROM python:3.12
RUN apt-get update && apt-get install -y libgl1-mesa-glx bash
WORKDIR /app
ENV PYTHONPATH=/app
COPY pyproject.toml poetry.lock /app/
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev
#COPY . /app
CMD ["/app/entrypoint.sh"]
