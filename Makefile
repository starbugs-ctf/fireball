
all: format typecheck lint

dev:
	uvicorn fireball.app:app --reload

format:
	black fireball
	black tests

lint:
	pylint fireball

typecheck:
	mypy fireball

test:
	pytest

.PHONY: dev format lint typecheck test
