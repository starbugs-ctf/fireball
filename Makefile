
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

.PHONY: dev format lint typecheck
