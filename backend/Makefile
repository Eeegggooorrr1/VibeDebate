POETRY ?= poetry
.PHONY: run-app update seed test
run-app:
	$(POETRY) run uvicorn vibedebate.main:create_app --factory --reload
update:
	$(POETRY) run alembic upgrade head
seed:
	$(POETRY) run vibedebate
test:
	$(POETRY) run pytest tests/current
