"""
Layer 1 tests: pure logical test for ingestion.imoprt_posts.process_post()

Strategies
- Using fake posts object to test ingestion.threads_api.download_image(), ingestion.threads_api.upload_image_to_s3()
  ingestion.threads_api.fetch_own_replies(), ingestion.threads_api.fetch_carousel_children()
- The tests are done in local database
- A cursor that automatically rollbacks is used in the tests

Execute: python -m pytest test/test_pipeline.py -v

"""

# %% Packages
import pytest
from unittest.mock import patch

import os
import psycopg
from ingestion.import_posts import process_post

# %% Functions
def get_testing_connection():
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
        host     = os.environ["TEST_DB_HOST"],
        port     = os.environ.get("DB_PORT", 5432),
        dbname   = os.environ["DB_NAME"],
        user     = os.environ["TEST_DB_USER"],
        password = os.environ["DB_PASSWORD"]
    )



@pytest.fixture
def db_cursor():
    """
    A cursor that automatically rollbacks after testing.
    
    Parameters
    ----------
    None
    
    Returns
    -------
    None
    
    """
    conn = get_testing_connection()
    cur  = conn.cursor()
    yield cur
    conn.rollback()
    cur.close()
    conn.close()



def make_fake_post(**overrides):
    """
    Making a fake post
    
    Parameters
    ----------
    **overrides
        contents of a fake post
    
    Returns
    -------
    base: dict
        fake post
    
    """
    base = {
        "username": "brownian.motion.99",
        "id": "test_post_001",
        "text": "《每天分享一個大氣科學知識直到我沒梗》這是一篇測試貼文",
        "timestamp": "2026-09-05T00:00:00+0000",
        "permalink": "https://threads.net/fake",
        "media_type": "IMAGE",
        "media_url": "https://fake.example.com/image.jpg",
        "is_quote_post": False,
    }
    base.update(overrides)
    
    return base



# %% Testing Objects
class TestProcessPostSingleImage:
    """
    Testing object for single image cases
    
    Parameters
    ----------
    None
    
    Cases
    -----
    I:   a post with only one image
    II:  a post begins with something else other than SERIES_TITLE
    III: a post with text is None
    
    """
    def test_inserts_post_and_image(self, db_cursor):
        """
        Case I: a post with only one image
        
        """
        fake_post = make_fake_post()

        with patch("ingestion.import_posts.download_image",
                   return_value = "media/test_post_001.jpg"), \
             patch("ingestion.import_posts.upload_image_to_s3",
                   return_value = "https://fake-bucket.s3.region.amazonaws.com/test_post_001.jpg") as mock_upload, \
             patch("ingestion.import_posts.fetch_own_replies", return_value = []):

            process_post(db_cursor, fake_post)

            db_cursor.execute(
                'SELECT id, text, media_type, is_quote_post FROM posts WHERE id = %s',
                (fake_post["id"],),
            )
            row = db_cursor.fetchone()
            assert row is not None
            assert row[0] == fake_post["id"]
            assert row[2] == "IMAGE"
            assert row[3] is False

            db_cursor.execute(
                "SELECT id, root_post_id, local_path FROM images WHERE id = %s",
                (fake_post["id"],),
            )
            image_row = db_cursor.fetchone()
            assert image_row is not None
            assert image_row[1] == fake_post["id"]
            assert image_row[2] == "https://fake-bucket.s3.region.amazonaws.com/test_post_001.jpg"

            # upload_image_to_s3() should be called only once for this case
            mock_upload.assert_called_once()

    
    
    def test_skips_post_without_series_title(self, db_cursor):
        """
        Case II: a post begins with something else other than SERIES_TITLE.
        
        """
        fake_post = make_fake_post(
            id   = "test_post_skip",
            text = "這篇不是系列文",
        )

        with patch("ingestion.import_posts.download_image") as mock_download, \
             patch("ingestion.import_posts.upload_image_to_s3") as mock_upload, \
             patch("ingestion.import_posts.fetch_own_replies") as mock_replies:

            process_post(db_cursor, fake_post)

            db_cursor.execute("SELECT id FROM posts WHERE id = %s", (fake_post["id"],))
            assert db_cursor.fetchone() is None

            mock_download.assert_not_called()
            mock_upload.assert_not_called()
            mock_replies.assert_not_called()

    
    
    def test_none_text_is_skipped(self, db_cursor):
        """
        Case III: a post with text is None (i.e. a post with only images or videos)
        
        """
        fake_post = make_fake_post(id = "test_post_none_text", text = None)

        with patch("ingestion.import_posts.download_image") as mock_download:
            process_post(db_cursor, fake_post)
            mock_download.assert_not_called()

            db_cursor.execute("SELECT id FROM posts WHERE id = %s", (fake_post["id"],))
            assert db_cursor.fetchone() is None



class TestProcessPostCarousel:
    """
    Testing object for multiple images cases.
    
    Parameters
    ----------
    None
    
    Cases
    -----
    I: a post with more than one images
    
    """
    def test_carousel_inserts_all_children_images(self, db_cursor):
        """
        Case I: a post with more than one images/videos
        
        """
        fake_post = make_fake_post(
            id         = "test_post_carousel",
            media_type = "CAROUSEL_ALBUM",
        )
        fake_post.pop("media_url", None)

        fake_children = [
            {"id": "child_1", "media_type": "IMAGE",
             "media_url": "https://fake.example.com/1.jpg"},
            {"id": "child_2", "media_type": "VIDEO",
             "media_url": "https://fake.example.com/2.mp4",
             "thumbnail_url": "https://fake.example.com/2_thumb.jpg"},
        ]

        with patch("ingestion.import_posts.fetch_carousel_children", return_value = fake_children), \
             patch("ingestion.import_posts.download_image", return_value = "media/fake.jpg"), \
             patch("ingestion.import_posts.upload_image_to_s3",
                   return_value = "https://fake-bucket.s3.region.amazonaws.com/fake.jpg") as mock_upload, \
             patch("ingestion.import_posts.fetch_own_replies", return_value=[]):

            process_post(db_cursor, fake_post)

            db_cursor.execute(
                "SELECT id FROM images WHERE root_post_id = %s ORDER BY id",
                (fake_post["id"],),
            )
            image_ids = [r[0] for r in db_cursor.fetchall()]
            assert image_ids == ["child_1", "child_2"]

            # child_1 (image) + child_2 (video + thumbnail) = 3
            assert mock_upload.call_count == 3



class TestProcessPostReplies:
    """
    Testing object for replies.
    
    Parameters
    ----------
    None
    
    Cases
    -----
    I:   a reply with correct username
    II:  a reply with incorrect username
    III: no replies
    
    """
    def test_inserts_own_replies_with_correct_root(self, db_cursor):
        """
        Case I: a reply with correct username
        
        """
        fake_post = make_fake_post(id = "test_post_with_replies")

        fake_replies = [
            {
                "id": "reply_1",
                "username": "brownian.motion.99",
                "text": "回覆內容 1",
                "timestamp": "2026-09-05T01:00:00+0000",
                "permalink": "https://threads.net/fake_reply_1",
                "media_type": "TEXT_POST",
                "is_quote_post": False,
            }
        ]

        with patch("ingestion.import_posts.download_image", return_value = "media/fake.jpg"), \
             patch("ingestion.import_posts.upload_image_to_s3",
                   return_value = "https://fake-bucket.s3.region.amazonaws.com/fake.jpg"), \
             patch("ingestion.import_posts.fetch_own_replies", return_value = fake_replies):

            process_post(db_cursor, fake_post)

            db_cursor.execute(
                "SELECT id, root_post_id FROM replies WHERE id = %s",
                ("reply_1",),
            )
            row = db_cursor.fetchone()
            assert row is not None
            assert row[1] == fake_post["id"]



    def test_no_replies_does_not_error(self, db_cursor):
        """
        Case III: no replies
        
        """
        fake_post = make_fake_post(id = "test_post_no_replies")

        with patch("ingestion.import_posts.download_image", return_value = "media/fake.jpg"), \
             patch("ingestion.import_posts.upload_image_to_s3",
                   return_value = "https://fake-bucket.s3.region.amazonaws.com/fake.jpg"), \
             patch("ingestion.import_posts.fetch_own_replies", return_value = []):

            process_post(db_cursor, fake_post)

            db_cursor.execute(
                "SELECT id FROM replies WHERE root_post_id = %s",
                (fake_post["id"],),
            )
            assert db_cursor.fetchall() == []