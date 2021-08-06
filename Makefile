
all: format typecheck lint

dev:
	uvicorn fireball.app:app --reload

prod:
	uvicorn fireball.app:app

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
