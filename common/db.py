# %% Packages
import os
import psycopg

# %% Global Variables
from dotenv import load_dotenv
load_dotenv()

# %% General Functions
def get_connection():
    """
    Getting a connection to database
    
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



def get_or_create_keyword_id(cur, word: str, category: str) -> int:
    """
    Getting or creating a keyword
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    word: str
        keyword
        
    category: str
        category of the keyword (general/specific)
        
    Returns
    -------
    keyword: str
        fetched keyword
    
    """
    cur.execute(
        """
        INSERT INTO keywords (word, category)
        VALUES (%s, %s)
        ON CONFLICT (word) DO UPDATE SET word = EXCLUDED.word
        RETURNING id
        """,
        (word, category),
    )
    return cur.fetchone()[0]



# %% For Specific Keywords
def merge_keywords(cur, duplicate_word: str, canonical_word: str, category: str = "specific"):
    """
    Merging duplicated keywords to canonical keywords.
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    duplicated_word: str
        duplicated keyword (marked by the user)
        
    canonical_word: str
        canonical keyword (specified by the user, if not exist, new keyword is created)
        
    Returns
    -------
    None
    
    """
    canonical_id = get_or_create_keyword_id(cur, canonical_word, category)

    cur.execute("SELECT id FROM keywords WHERE word = %s AND category = %s", (duplicate_word, category))
    row = cur.fetchone()
    if row is None:
        print(f"  找不到 '{duplicate_word}'，略過")
        return
    duplicate_id = row[0]

    if duplicate_id == canonical_id:
        print(f"  '{duplicate_word}' 跟 '{canonical_word}' 本來就是同一筆，略過")
        return

    cur.execute(
        """
        INSERT INTO post_keywords (post_id, keyword_id)
        SELECT post_id, %s FROM post_keywords WHERE keyword_id = %s
        ON CONFLICT DO NOTHING
        """,
        (canonical_id, duplicate_id),
    )

    cur.execute("DELETE FROM keywords WHERE id = %s", (duplicate_id,))
    print(f"  已將 '{duplicate_word}' 合併進 '{canonical_word}'")
    
    

def delete_keyword(cur, word: str, category: str = "specific"):
    """
    Deleting the duplicated keyword.
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    word: str
        keyword
        
    category: str = "specific"
        keyword category
        
    Returns
    -------
    None
    
    """
    cur.execute("DELETE FROM keywords WHERE word = %s AND category = %s", (word, category))


    
def mark_as_reviewed(cur, words: list[str], category: str = "specific"):
    """
    Marking keywords as reviewed.
    
    Parameters
    ----------
    cur: psycopg.Cursor object
        Database cursor
        
    words: list[str]
        Reviewd keywords
        
    category: str = "specific"
        Keyword category
        
    Returns
    -------
    None
    
    """
    cur.execute(
        "UPDATE keywords SET reviewed = TRUE WHERE word = ANY(%s) AND category = %s",
        (words, category),
    )