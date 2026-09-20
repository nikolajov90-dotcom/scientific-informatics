FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./

RUN pip install poetry

RUN poetry config virtualenvs.create false

RUN poetry install --only main --no-root

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]