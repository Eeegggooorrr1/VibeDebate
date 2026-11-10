COMPOSE ?= docker compose
WAIT_TIMEOUT ?= 240
.NOTPARALLEL:
.PHONY: up down migrate seed test logs ps
up:
	$(COMPOSE) build backend test frontend frontend-test
	$(COMPOSE) stop frontend backend
	$(COMPOSE) rm -f test frontend-test migrate seed keycloak-theme
	$(COMPOSE) up -d --wait --wait-timeout $(WAIT_TIMEOUT) frontend
	@echo Frontend: http://localhost:5173
	@echo API: http://localhost:8000/docs
	@echo Keycloak: http://localhost:8180
down:
	$(COMPOSE) down
migrate:
	$(COMPOSE) stop frontend backend
	$(COMPOSE) run --rm --build migrate
seed:
	$(COMPOSE) stop frontend backend
	$(COMPOSE) run --rm --build seed
test:
	$(COMPOSE) build test frontend-test
	$(COMPOSE) run --rm test
	$(COMPOSE) run --rm --no-deps frontend-test
logs:
	$(COMPOSE) logs -f backend frontend
ps:
	$(COMPOSE) ps -a
