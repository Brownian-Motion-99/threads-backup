import os
from dotenv import load_dotenv
import psycopg
import requests
import time

load_dotenv()
ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
BASE_URL = "https://graph.threads.net/v1.0"


def safe_get(url, params=None):
    time.sleep(0.5)
    response = requests.get(url, params=params)
    if response.status_code == 429:
        wait_seconds = int(response.headers.get("Retry-After", 60))
        time.sleep(wait_seconds)
        response = requests.get(url, params=params)
    response.raise_for_status()
    return response


def fetch_is_quote_post(item_id):
    url = f"{BASE_URL}/{item_id}"
    params = {"fields": "is_quote_post", "access_token": ACCESS_TOKEN}
    data = safe_get(url, params=params).json()
    return data.get("is_quote_post", False)


def backfill_table(cur, table_name):
    cur.execute(f"SELECT id FROM {table_name}")
    ids = [row[0] for row in cur.fetchall()]

    print(f"開始補齊 {table_name}，共 {len(ids)} 筆")
    for item_id in ids:
        is_quote = fetch_is_quote_post(item_id)
        cur.execute(
            f"UPDATE {table_name} SET is_quote_post = %s WHERE id = %s",
            (is_quote, item_id),
        )
        if is_quote:
            print(f"  {item_id} 是引用貼文")


def main():
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        backfill_table(cur, "posts")
        backfill_table(cur, "replies")
    conn.commit()
    conn.close()
    print("補齊完成")


if __name__ == "__main__":
    main()