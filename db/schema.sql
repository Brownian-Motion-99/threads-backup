CREATE TABLE posts (
    id          TEXT PRIMARY KEY,
    text        TEXT,
    "timestamp" TIMESTAMPTZ NOT NULL,
    permalink   TEXT NOT NULL,
    media_type  TEXT NOT NULL
);

CREATE TABLE replies (
    id           TEXT PRIMARY KEY,
    root_post_id TEXT NOT NULL REFERENCES posts ON DELETE CASCADE,
    text         TEXT,
    "timestamp"  TIMESTAMPTZ NOT NULL,
    permalink    TEXT NOT NULL,
    media_type   TEXT NOT NULL
);

CREATE TABLE images (
    id            TEXT PRIMARY KEY,
    root_post_id  TEXT REFERENCES posts ON DELETE CASCADE,
    root_reply_id TEXT REFERENCES replies ON DELETE CASCADE,
    local_path    TEXT NOT NULL,
    CHECK (
        (root_post_id IS NOT NULL AND root_reply_id IS NULL)
        OR
        (root_post_id IS NULL AND root_reply_id IS NOT NULL)
    )
);

ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_quote_post BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE replies ADD COLUMN IF NOT EXISTS is_quote_post BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE keywords (
    id       SERIAL PRIMARY KEY,
    word     TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL DEFAULT 'specific'
        CHECK (category IN ('general', 'specific')),
    reviewed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE post_keywords (
    post_id    TEXT REFERENCES posts ON DELETE CASCADE,
    keyword_id INTEGER REFERENCES keywords ON DELETE CASCADE,
    PRIMARY KEY (post_id, keyword_id)
);