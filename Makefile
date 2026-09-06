.PHONY: db import schema awssync

db:
	docker exec -it threads-backup-db psql -U postgres -d threads_backup

import:
	python -m ingestion.import_posts

schema:
	docker exec -i threads-backup-db psql -U postgres -d threads_backup < db/schema.sql

backfill:
	python -m ingestion.backfill_quote_post

awssync:
	/Users/prcpltwfkwd/.local/bin/aws s3 cp ./frontend s3://threads-backup-frontend --recursive --exclude "*" --include "*.html" --content-type "text/html; charset=utf-8"