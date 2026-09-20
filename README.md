# Scientific Informatics

Backend API for genomic variant analysis.

## Project Overview

This project is a backend application for uploading, processing, annotating, and analyzing genomic variant data.

The application is developed as part of the EPAM Scientific Informatics training program.

## Technologies

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL
- Poetry
- Docker
- Docker Compose
- Pytest
- Ruff
- GitHub Actions

## Project Structure

```text
scientific-informatics/
├── app/
│   ├── api/
│   │   └── routes/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
├── README.md
└── .gitignore


Requirements

To run the project locally, install:

Python 3.12 or later
Poetry
Docker
Docker Compose
Git
Installation

Clone the repository:

git clone <repository-url>
cd scientific-informatics

Install Python dependencies with Poetry:

poetry install
Run Locally

Start the FastAPI application:

poetry run uvicorn app.main:app --reload

The API will be available at:

http://localhost:8000

Interactive API documentation:

http://localhost:8000/docs
Run with Docker Compose

Build the Docker image and start the application and PostgreSQL database:

docker compose up --build

The following services are started:

FastAPI application on port 8000
PostgreSQL database on port 5432

To stop the services:

docker compose down
Current API

The initial API provides a health-check endpoint:

GET /

Example response:

{
  "message": "Scientific Informatics API"
}
Development

Run tests:

poetry run pytest

Run Ruff:

poetry run ruff check .

Format the code:

poetry run ruff format .
Project Status

The project is currently under development.

Planned functionality includes:

Project management
VCF file upload and parsing
Variant extraction
ClinVar annotation
Variant filtering and analysis
PostgreSQL data storage
AWS S3 integration
AWS RDS PostgreSQL
Docker container deployment
AWS ECS Fargate deployment
CI/CD automation

###