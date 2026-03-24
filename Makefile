.PHONY: install sync test dev clean help fmt lint typecheck install-tool

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: sync ## Full setup: sync deps
	@echo "Done. Run 'make test' to verify."

sync: ## Sync Python dependencies
	uv sync

test: ## Run tests
	uv run python -m pytest tests/ -v

fmt: ## Format code with ruff
	uv run ruff format src/ tests/

lint: ## Lint code with ruff
	uv run ruff check src/ tests/

typecheck: ## Type check with pyright
	uv run python -m pyright src/ tests/

dev: install test ## Setup dev environment and run tests

install-tool: install ## Install as global uv tool
	uv tool install . --reinstall

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
