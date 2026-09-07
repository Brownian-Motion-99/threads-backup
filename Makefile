.PHONY: db import schema deploy-frontend

db:
	docker exec -it threads-backup-db psql -U postgres -d threads_backup

import:
	python -m ingestion.import_posts

schema:
	docker exec -i threads-backup-db psql -U postgres -d threads_backup < db/schema.sql

backfill:
	python -m ingestion.backfill_quote_post

deploy-frontend:
	/Users/prcpltwfkwd/.local/bin/aws s3 cp ./frontend s3://threads-backup-frontend --recursive --exclude "*" --include "*.html" --content-type "text/html; charset=utf-8"
	/Users/prcpltwfkwd/.local/bin/aws s3 cp ./frontend s3://threads-backup-frontend --recursive --exclude "*" --include "*.js" --content-type "text/javascript; charset=utf-8"
	/Users/prcpltwfkwd/.local/bin/aws s3 cp ./frontend s3://threads-backup-frontend --recursive --exclude "*" --include "*.css" --content-type "text/css; charset=utf-8"
	/Users/prcpltwfkwd/.local/bin/aws s3 cp ./frontend/robots.txt s3://threads-backup-frontend/robots.txt --content-type "text/plain"
	/Users/prcpltwfkwd/.local/bin/aws cloudfront create-invalidation --distribution-id E26ZJCZ83G0UUH --paths "/*"