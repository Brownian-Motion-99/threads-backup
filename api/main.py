# %% Packages
import os
import psycopg
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# %% Global Variables
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
)

DB_READER_HOST    = os.environ["DB_READER_HOST"]
DB_READER_PORT    = os.environ["DB_READER_PORT"]
DEFAULT_PAGE_SIZE = 20
MAXIMUM_PAGE_SIZE = 50

# %% Functions
def get_readonly_connection():
    """
    Getting a read-only connection to database
    
    Parameters
    ----------
    None
    
    Returns
    -------
    psycopg.connect object
    
    """
    return psycopg.connect(
        host     = os.environ["DB_READER_HOST"],
        port     = os.environ["DB_READER_PORT"],
        dbname   = os.environ["DB_NAME"],
        user     = os.environ["DB_READER_USER"],
        password = os.environ["DB_READER_PASSWORD"],
        options = "-c statement_timeout=5000",
    )



def build_posts(cur: psycopg.Cursor, post_rows: list):
    """
    Function that builds a post list.
    
    Parameters
    ----------
    cur: psycopg.Cursor
    
    post_rows: list
        A list containing rows from a table.
        
    Returns
    -------
    posts: list
        A list of dictionaries of posts.
    
    """
    if not post_rows:
        return []
    
    post_ids = [row[0] for row in post_rows]
    
    cur.execute(
        "SELECT root_post_id, local_path FROM images WHERE root_post_id = ANY(%s)",
        (post_ids,)
    )
    image_rows = cur.fetchall()
    
    cur.execute(
        """
        SELECT pk.post_id, k.word
        FROM post_keywords pk
        JOIN keywords k ON pk.keyword_id = k.id
        WHERE pk.post_id = ANY(%s) AND k.category = 'general'
        """,
        (post_ids,)
    )
    keyword_rows = cur.fetchall()
    
    images_by_post = {}
    for root_post_id, local_path in image_rows:
        image_url = f"{local_path}"
        images_by_post.setdefault(root_post_id, []).append(image_url)
    
    keywords_by_post = {}
    for post_id, word in keyword_rows:
        keywords_by_post.setdefault(post_id, []).append(word)
    
    posts = []
    for row in post_rows:
        post_id = row[0]
        posts.append({
            "id": post_id,
            "text": row[1],
            "timestamp": row[2].isoformat(),
            "images": images_by_post.get(post_id, []),
            "keywords": keywords_by_post.get(post_id, []),
        })
    
    return posts



# %% get functions
@app.get("/")
def read_root():
    return {"message": "Hello from Threads Backup API"}



@app.get("/posts")
def get_posts(limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """
    Main workhorse API for homepage.
    Fetching posts from the database, returning a list of dictionaries.
    
    Parameters
    ----------
    limit: int
        Number of posts in each page.
        
    offset:
        Number of posts skipped while fetching posts.
    
    Returns
    -------
    posts: list
        The list that containing all of the posts.
        Each post is stored in a dictionary, including id, text, timestamp, images and general keywords.
    
    """
    limit = min(limit, MAXIMUM_PAGE_SIZE)
    
    conn = get_readonly_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, text, timestamp FROM posts ORDER BY timestamp DESC LIMIT %s OFFSET %s",
        (limit + 1, offset)
    )
    post_rows = cur.fetchall()

    has_more = len(post_rows) > limit
    post_rows = post_rows[:limit]

    posts = build_posts(cur, post_rows)

    cur.close()
    conn.close()
        
    return {"posts": posts, "has_more": has_more}



@app.get("/keywords")
def get_keywords():
    """
    Fetching general keywords with post counts.
    
    Parameters
    ----------
    None
    
    Returns
    -------
    keywords: dict
        A dictionary containing general keywords.
    
    """
    conn = get_readonly_connection()
    cur  = conn.cursor()

    cur.execute(
        """
        SELECT k.word, COUNT(DISTINCT pk.post_id)
        FROM keywords k
        LEFT JOIN post_keywords pk ON pk.keyword_id = k.id
        WHERE k.category = 'general'
        GROUP BY k.word
        ORDER BY k.word
        """
    )
    general = [{"word": row[0], "count": row[1]} for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    keywords = {"general": general}
    
    return keywords



@app.get("/posts/search")
def search_posts(
    q: str = None, 
    keywords: list[str] = Query(default=None), 
    mode: str = "or", 
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
):
    """
    Searching posts by optioinal keyword filter and/or optional text search.
    
    Parameters
    ----------
    type: str
        Type of searching, "keyword" or "text"
    
    q: str
        Query
        
    keywords: list
        List of keywords
        
    mode: str
        Determine the logic of applying multiple keywords
        
    Returns
    -------
    posts: list
        List of post dictionaries that match the query
    
    """
    limit = min(limit, MAXIMUM_PAGE_SIZE)
    
    conn = get_readonly_connection()
    cur  = conn.cursor()

    conditions = []
    params     = []

    if keywords:
        if mode == "and":
            cur.execute(
                """
                SELECT DISTINCT p.id, p.text, p.timestamp
                FROM posts p
                JOIN post_keywords pk ON p.id = pk.post_id
                JOIN keywords k ON pk.keyword_id = k.id
                WHERE k.category = 'general' AND k.word = ANY(%s)
                GROUP BY p.id, p.text, p.timestamp
                HAVING COUNT(DISTINCT k.word) = %s
                ORDER BY p.timestamp DESC
                """,
                (keywords, len(keywords))
            )
        else:
            cur.execute(
                """
                SELECT DISTINCT p.id, p.text, p.timestamp
                FROM posts p
                JOIN post_keywords pk ON p.id = pk.post_id
                JOIN keywords k ON pk.keyword_id = k.id
                WHERE k.category = 'general' AND k.word = ANY(%s)
                ORDER BY p.timestamp DESC
                """,
                (keywords,)
            )
        matches_ids = [row[0] for row in cur.fetchall()]
        if not matches_ids:
            cur.close()
            conn.close()
            return {"posts": [], "has_more": False}
        conditions.append("id = ANY(%s)")
        params.append(matches_ids)

    if q:
        conditions.append("text ILIKE %s")
        params.append(f"%{q}%")

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    cur.execute(
        f"""
        SELECT id, text, timestamp FROM posts
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT %s OFFSET %s
        """,
        params + [limit + 1, offset]
    )

    post_rows = cur.fetchall()
    has_more  = len(post_rows) > limit
    post_rows = post_rows[:limit]

    posts = build_posts(cur, post_rows)

    cur.close()
    conn.close()
    
    return {"posts": posts, "has_more": has_more}



@app.get("/posts/{post_id}")
def get_post(post_id: str):
    """
    Main workhorse API for single post page.
    Given a post id, fetching a post from the database, returning a dictionary.
    
    Parameters
    ----------
    post_id: str
        id of a post
        
    Returns
    -------
    post: dict
        A dictionary including id, text, timestamp, images, replies, keywords and permanent link.
    
    """
    # --- Retrieve data from database --- #
    conn = get_readonly_connection()
    cur  = conn.cursor()

    # Fetching a post
    cur.execute(
        "SELECT id, text, timestamp, permalink, is_quote_post FROM posts WHERE id = %s",
        (post_id,)
    )
    post_row = cur.fetchone()

    if post_row is None:
        cur.close()
        conn.close()
        return {"error": "Post not found"}

    # Fetching images in a post
    cur.execute(
        "SELECT local_path FROM images WHERE root_post_id = %s",
        (post_id,)
    )
    post_images = [row[0] for row in cur.fetchall()]
    
    # Fetching keywords in a post
    cur.execute(
        """
        SELECT k.word, k.category
        FROM post_keywords pk
        JOIN keywords k ON pk.keyword_id = k.id
        WHERE pk.post_id = %s
        """,
        (post_id,)
    )
    keyword_rows = cur.fetchall()

    # Fetching replies in a post
    cur.execute(
        "SELECT id, text, timestamp, is_quote_post FROM replies WHERE root_post_id = %s ORDER BY timestamp ASC",
        (post_id,)
    )
    reply_rows = cur.fetchall()

    # Fetching images in the replies
    cur.execute(
        """
        SELECT root_reply_id, local_path FROM images
        WHERE root_reply_id IN (
            SELECT id FROM replies WHERE root_post_id = %s
        )
        """,
        (post_id,)
    )
    images_by_reply = {}
    for root_reply_id, local_path in cur.fetchall():
        image_url = f"{local_path}"
        images_by_reply.setdefault(root_reply_id, []).append(image_url)

    cur.close()
    conn.close()
    # --- Retrieve data from database --- #
    
    # --- Handling keywords --- #
    general_keywords  = [word for word, category in keyword_rows if category == "general"]
    specific_keywords = [word for word, category in keyword_rows if category == "specific"]
    # --- Handling keywords --- #

    # --- Handling replies --- #
    replies = []
    for row in reply_rows:
        reply_id = row[0]
        replies.append({
            "id": reply_id,
            "text": row[1],
            "timestamp": row[2].isoformat(),
            "images": images_by_reply.get(reply_id, []),
            "is_quote_post": row[3],
        })
    # --- Handling replies --- #

    # --- Returning detail post as a dictionary --- #
    post = {
        "id": post_row[0],
        "text": post_row[1],
        "timestamp": post_row[2].isoformat(),
        "permalink": post_row[3],
        "is_quote_post": post_row[4],
        "images": post_images,
        "keywords": {
            "general": general_keywords,
            "specific": specific_keywords,
        },
        "replies": replies,
    }
    # --- Returning detail post as a dictionary --- #
    return post