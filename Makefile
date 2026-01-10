# Variables
PYTHON = .venv/bin/python
PIP = .venv/bin/pip
DOCKER_COMPOSE = docker-compose

.PHONY: help install run docker-up docker-down clean test

help:
	@echo "Available commands:"
	@echo "  make install     - Set up virtual environment and install dependencies"
	@echo "  make run         - Run the FastAPI server locally with reload"
	@echo "  make docker-up   - Build and start all containers (API + MongoDB)"
	@echo "  make docker-down - Stop and remove all containers"
	@echo "  make clean       - Remove cache files and virtual environment"
	@echo "  make test        - Run tests using pytest"

# Local Development Setup
install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Initialization complete. Use 'source .venv/bin/activate' to start."

run:
	$(PYTHON) -m uvicorn app:app --reload --host 127.0.0.1 --port 8000

# Docker Operations
docker-up:
	$(DOCKER_COMPOSE) up --build -d
	@echo "Services are running at http://localhost:8000"

docker-down:
	$(DOCKER_COMPOSE) down

# Maintenance
clean:
	rm -rf .venv
	rm -rf .vector_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete."

test:
	$(PYTHON) -m pytest