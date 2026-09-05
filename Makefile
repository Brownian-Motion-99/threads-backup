.PHONY: db import schema

db:
	docker exec -it threads-backup-db psql -U postgres -d threads_backup

import:
	python -m ingestion.import_posts

schema:
	docker exec -i threads-backup-db psql -U postgres -d threads_backup < db/schema.sql

backfill:
	python -m ingestion.backfill_quote_post