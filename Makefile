.PHONY: help backend-test frontend-install frontend-build check

help:
	@printf "Available targets:\n"
	@printf "  backend-test      Run backend tests\n"
	@printf "  frontend-install  Install frontend dependencies\n"
	@printf "  frontend-build    Build frontend\n"
	@printf "  check             Run available checks\n"

backend-test:
	cd backend && .venv/bin/python -m pytest

frontend-install:
	cd frontend && npm install

frontend-build:
	cd frontend && npm run build

check: backend-test frontend-build

