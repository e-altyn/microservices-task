.PHONY: up down logs test demo
up:
	docker compose up --build -d --wait

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

demo:
	python scripts/demo.py
