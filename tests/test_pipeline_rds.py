"""
Layer 2 tests: testing schema on RDS

Features that have been tested in layer 1 will not be tested in layer 2.
Layer 2 tests are performed in order to test if these features work in RDS environment.

Execute (users should manually specify the connection parameters):

    DB_HOST=<RDS writer endpoint> \\
    DB_PORT=5432 \\
    DB_NAME=<database name> \\
    DB_USER=<RDS account> \\
    DB_PASSWORD=<RDS password> \\
    python -m pytest tests/test_pipeline_rds.py -v -s

"""

# %%
import os
from unittest.mock import patch

import pytest
import psycopg

# from common.db import get_connection
from ingestion.import_posts import process_post
from tests.test_pipeline import make_fake_post

# %% Functions

def get_rds_testing_connection():
    """
    Getting testing a connection to database
    
    Parameters
    ----------
    None
    
    Returns
    -------
    psycopg.connect object
    
    """
    return psycopg.connect(
        host     = os.environ["DB_HOST"],
        port     = os.environ["DB_PORT"],
        dbname   = os.environ["DB_NAME"],
        user     = os.environ["DB_USER"],
        password = os.environ["DB_PASSWORD"]
    )



@pytest.fixture
def db_cursor_rds():
    """
    Getting testing a connection to database
    
    Parameters
    ----------
    None
    
    Returns
    -------
    psycopg.connect object

    """
    db_host = os.environ.get("DB_HOST", "")
    if db_host in ("", "localhost", "127.0.0.1"):
        pytest.fail(
            "DB_HOST: f'{db_host!r}'"
            "The host looks like a local host."
        )

    print(f"\n[Layer 2] host: {db_host}")  # -v -s

    conn = get_rds_testing_connection()
    cur = conn.cursor()
    yield cur
    conn.rollback()
    cur.close()
    conn.close()



# %% Testing Objects
class TestRDSSingleImageConstraints:
    def test_insert_post_and_image_respects_xor_check(self, db_cursor_rds):
        """
        XOR CHECK constraint in TABLE images.
        i.e. an image can only belong to either post or reply
        
        """
        fake_post = make_fake_post(id="rds_test_post_001")

        with patch("ingestion.import_posts.download_image",
                   return_value = "media/rds_test_post_001.jpg"), \
             patch("ingestion.import_posts.upload_image_to_s3",
                   return_value = "https://fake-bucket.s3.region.amazonaws.com/rds_test_post_001.jpg"), \
             patch("ingestion.import_posts.fetch_own_replies", return_value = []):

            process_post(db_cursor_rds, fake_post)

            db_cursor_rds.execute(
                "SELECT id, root_post_id, root_reply_id FROM images WHERE id = %s",
                (fake_post["id"],),
            )
            row = db_cursor_rds.fetchone()
            assert row is not None
            assert row[1] == fake_post["id"]  # root_post_id must not be null
            assert row[2] is None             # root_reply_id must be null


class TestRDSCascadeDelete:
    def test_deleting_root_post_cascades_to_replies(self, db_cursor_rds):
        """
        Testing if root post deletion cascades to replies.
        
        """
        fake_post = make_fake_post(id="rds_test_post_cascade")
        fake_replies = [
            {
                "id": "rds_test_reply_cascade",
                "text": "測試 cascade 用的回覆",
                "timestamp": "2026-09-05T01:00:00+0000",
                "permalink": "https://threads.net/fake_rds_reply",
                "media_type": "TEXT_POST",
                "is_quote_post": False,
            }
        ]

        with patch("ingestion.import_posts.download_image",
                   return_value = "media/rds_test_post_cascade.jpg"), \
             patch("ingestion.import_posts.upload_image_to_s3",
                   return_value = "https://fake-bucket.s3.region.amazonaws.com/rds_test_post_cascade.jpg"), \
             patch("ingestion.import_posts.fetch_own_replies", return_value = fake_replies):

            process_post(db_cursor_rds, fake_post)

            db_cursor_rds.execute(
                "SELECT id FROM replies WHERE id = %s", ("rds_test_reply_cascade",)
            )
            assert db_cursor_rds.fetchone() is not None

            db_cursor_rds.execute(
                "DELETE FROM posts WHERE id = %s", (fake_post["id"],)
            )

            db_cursor_rds.execute(
                "SELECT id FROM replies WHERE id = %s", ("rds_test_reply_cascade",)
            )
            assert db_cursor_rds.fetchone() is None, (
                "CASCADE 沒有生效：刪除 root post 之後，reply 應該要跟著消失"
            )