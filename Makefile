# markdownland — common tasks. Run `make` for the list.
.DEFAULT_GOAL := help
.PHONY: help uv-sync run dev test lint fmt docker-build docker-run clean

help: ## Show this help
	@echo "markdownland — available commands:"
	@echo
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

uv-sync: ## Install/sync dependencies into the uv environment
	uv sync

run: uv-sync ## Run the server (Granian)
	uv run markdownland

dev: uv-sync ## Run the server with autoreload
	RELOAD=1 uv run markdownland

test: uv-sync ## Run the test suite
	uv run pytest

lint: uv-sync ## Lint with ruff
	uv run ruff check .

fmt: uv-sync ## Format with ruff
	uv run ruff format .

docker-build: ## Build the Docker image
	docker build -t markdownland .

docker-run: docker-build ## Build and run the Docker image on :8000
	docker run --rm -p 8000:8000 markdownland

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache __pycache__ */__pycache__
