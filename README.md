# Fireball

<!-- Insert cool image here -->

## Development

### Poetry

This project uses [Poetry](https://python-poetry.org) to manage Python dependencies.

Useful links:

- [Installation](https://python-poetry.org/docs/#installation)
- [Basic usage](https://python-poetry.org/docs/basic-usage/)

Useful commands:

- `poetry add <package>` to add new dependency
- `poetry install` to install dependencies
- `poetry shell` to run in a virtual environment

### Make

NOTE: You will need to run most of these commands in a virtual env created by [Poetry](#Poetry)

- `make dev` will run a dev server that will automatically restart on fs changes
- `make lint` will run `pylint`
- `make typecheck` will run `mypy`
- `make format` will run `black` formatter

### Links to package docs

- `fastapi`
  - <https://fastapi.tiangolo.com/>
  - <https://fastapi.tiangolo.com/advanced/async-sql-databases/>
- `aiodocker`
  - <https://aiodocker.readthedocs.io/en/latest/>

## Testing

**TODO**

## Deployment

See `fireball/config.py` for configuration variables

## Docs

You can see swagger schema at `/docs` when running the dev server
