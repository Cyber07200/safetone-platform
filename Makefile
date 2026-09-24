.PHONY: start backend frontend test test-backend test-frontend build serve migrate

start:            ## backend + frontend в режиме разработки
	./start.sh

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && . .venv/bin/activate && alembic upgrade head

test: test-backend test-frontend

test-backend:
	cd backend && . .venv/bin/activate && pytest -q

test-frontend:
	cd frontend && npm test

build:            ## собрать frontend в frontend/dist
	cd frontend && npm run build

serve: build      ## один процесс: backend раздаёт собранный frontend на :8000
	cd backend && . .venv/bin/activate && uvicorn app.main:app --port 8000
