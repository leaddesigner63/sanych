up:
	docker compose -f infra/docker-compose.yml --env-file infra/.env up --build -d
