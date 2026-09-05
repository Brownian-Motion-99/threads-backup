from anthropic import APIStatusError
from common.db import get_connection

def run_tagging_job(fetch_posts_fn, tag_post_fn, limit=None):
    """
    共用的標記任務執行器，general/specific tagger 都會用到。

    fetch_posts_fn(cur, limit) -> 回傳一個 list，每個元素是一個 tuple，
        第一個欄位一定要是 post_id（用來印 log）。
    tag_post_fn(cur, *row) -> 對一篇貼文做標記，回傳結果（用於印出 log）。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            rows = fetch_posts_fn(cur, limit)
            print(f"共 {len(rows)} 篇貼文待處理")

            for row in rows:
                post_id = row[0]
                try:
                    result = tag_post_fn(cur, *row)
                except APIStatusError as e:
                    print(f"API 呼叫失敗，狀態碼 {e.status_code}")
                    print(f"詳細內容：{e.response.text}")
                    print("已處理的部分已經存好了，補值後重新執行即可從中斷處繼續。")
                    break
                conn.commit()
                print(f"[{post_id}] → {result}")
    finally:
        conn.close()
        print("連線已關閉")