# %% Packages
from common.db import get_connection
from ingestion.threads_api import (
    fetch_posts_page,
    fetch_carousel_children,
    fetch_own_replies,
    download_image,
    upload_image_to_s3,
    BASE_URL,
    ACCESS_TOKEN,
    BUCKET_NAME,
    PROFILE_NAME,
    AWS_REGION,
)

# %% Global Variables
SERIES_TITLE = "《每天分享一個大氣科學知識直到我沒梗》"

# %% Functions
def insert_post(cur, post):
    """
    Inserting a post into TABLE posts.
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    post: dict
        A dictionary containing a post and its associated attributes
        
    Returns
    -------
    None
    
    """
    cur.execute(
        """
        INSERT INTO posts (id, text, "timestamp", permalink, media_type, is_quote_post)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            post["id"],
            post.get("text"),
            post["timestamp"],
            post["permalink"],
            post["media_type"],
            post.get("is_quote_post", False),
        ),
    )


def insert_reply(cur, reply, root_post_id):
    """
    Inserting a reply into TABLE replies.
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    reply: dict
        A dictionary containing a reply and its associated attributes
        
    root_post_id: str
        The id of the root post
        
    Returns
    -------
    None
    
    """
    cur.execute(
        """
        INSERT INTO replies (id, root_post_id, text, "timestamp", permalink, media_type, is_quote_post)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            reply["id"],
            root_post_id,
            reply.get("text"),
            reply["timestamp"],
            reply["permalink"],
            reply["media_type"],
            reply.get("is_quote_post", False),
        ),
    )


def insert_image(cur, image_id, s3_url, post_id = None, reply_id = None):
    """
    Inserting an image/video into TABLE images.
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    image_id: str
        The id of the medium
        
    s3_url: str
        The AWS S3 url of the medium
        
    post_id: str = None
        The id of the post
        
    reply_id: str = None
        The id of the reply
        
    root_post_id: str
        The id of the root post
        
    Returns
    -------
    None
    
    Notes
    -----
    COLUMN local_path is named as "local_path",
    but it stores the S3 urls of the media
    
    """
    cur.execute(
        """
        INSERT INTO images (id, root_post_id, root_reply_id, local_path)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (image_id, post_id, reply_id, s3_url),
    )


def process_post(cur, post):
    """
    The main workhorse function
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    post: dict
        A dictionary containing a post and its associated attributes
        
    Returns
    -------
    None
    
    """
    # Sanity check
    text = post.get("text")
    if text is None or not text.strip().startswith(SERIES_TITLE):
        return

    # Inserting the main post
    insert_post(cur, post)

    # Handling the media
    media_type = post["media_type"]
    
    ## More than one image/video
    if media_type == "CAROUSEL_ALBUM":
        children = fetch_carousel_children(post["id"])
        
        for child in children:
            local_path = download_image(child["id"], child["media_url"], child["media_type"])
            s3_url     = upload_image_to_s3(local_path, PROFILE_NAME, BUCKET_NAME, AWS_REGION)
            insert_image(cur, child["id"], s3_url, post_id = post["id"])
            
            # The thumbnail of the video will be uploaded to S3,
            # but it will NOT be inserted into the database
            if child["media_type"] == "VIDEO" and child.get("thumbnail_url"):
                local_path = download_image(child["id"], child["thumbnail_url"], "IMAGE")
                s3_url     = upload_image_to_s3(local_path, PROFILE_NAME, BUCKET_NAME, AWS_REGION)
    
    # Only one image/video
    elif media_type in ("IMAGE", "VIDEO") and post.get("media_url"):
        
        local_path = download_image(post["id"], post["media_url"], media_type)
        s3_url     = upload_image_to_s3(local_path, PROFILE_NAME, BUCKET_NAME, AWS_REGION)
        insert_image(cur, post["id"], s3_url, post_id = post["id"])
        
        if media_type == "VIDEO" and post.get("thumbnail_url"):
            local_path = download_image(post["id"], post["thumbnail_url"], "IMAGE")
            s3_url     = upload_image_to_s3(local_path, PROFILE_NAME, BUCKET_NAME, AWS_REGION)

    # Inserting the replies
    for reply in fetch_own_replies(post["id"]):
        insert_reply(cur, reply, root_post_id=post["id"])

# %% Main
def main():
    conn = get_connection()

    url = f"{BASE_URL}/me/threads"
    params = {
        "fields": "id,text,timestamp,permalink,media_type,media_url,thumbnail_url,is_quote_post",
        "limit": 25,
        "access_token": ACCESS_TOKEN,
    }
    first_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    with conn.cursor() as cur:
        next_url = first_url
        while next_url:
            posts, next_url = fetch_posts_page(next_url)
            for post in posts:
                process_post(cur, post)
            conn.commit()
            print(f"這一頁處理完成，共 {len(posts)} 篇貼文")

    conn.close()
    print("全部匯入完成")


if __name__ == "__main__":
    main()