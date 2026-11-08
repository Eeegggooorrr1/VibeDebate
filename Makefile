.PHONY: up down migrate seed test
up:
	docker compose up -d --wait
down:
	docker compose down
migrate:
	$(MAKE) -C backend update
seed:
	$(MAKE) -C backend seed
test:
	$(MAKE) -C backend test
