FROM python:3.12
WORKDIR /app
ENV PYTHONPATH=/app
COPY pyproject.toml poetry.lock /app/
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev
#COPY . /app
CMD ["/app/entrypoint.sh"]
