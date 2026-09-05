from common.db import get_connection
from tagging.specific_tagger import (
    build_full_context,
    extract_specific_keywords,
    get_existing_specific_keywords,
)

MODELS_TO_COMPARE = ["claude-haiku-4-5-20251001", "claude-sonnet-5"]
OUTPUT_DIR = "tagging/comparison_results"


def fetch_sample_posts(cur, limit: int = 5):
    """抓幾篇貼文（含底下回覆合併文字）當作測試樣本，不篩選是否已標記過。"""
    cur.execute(
        """
        SELECT
            p.id,
            p.text,
            string_agg(r.text, E'\n---\n' ORDER BY r."timestamp") AS replies_text
        FROM posts p
        LEFT JOIN replies r ON r.root_post_id = p.id
        WHERE p.text IS NOT NULL
        GROUP BY p.id, p.text
        ORDER BY p."timestamp" DESC
        LIMIT %s
        """,
        (limit,),
    )
    return cur.fetchall()


def save_comparison_file(post_id, post_text, replies_text, results):
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{post_id}.md")

    lines = [f"# 貼文 {post_id}", "", "## 貼文內容", post_text or "（無文字）", ""]
    if replies_text:
        lines += ["## 回覆內容", replies_text, ""]

    lines.append("## 各模型生成的 specific tag")
    for model, keywords in results.items():
        lines.append(f"- **{model}**：{keywords}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  已存檔：{path}")


def compare(limit: int = 5):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            posts = fetch_sample_posts(cur, limit=limit)

            for post_id, text, replies_text in posts:
                # 每篇都重新查一次現有 specific 關鍵字，跟正式流程的行為保持一致
                existing_keywords = get_existing_specific_keywords(cur)
                full_context = build_full_context(text, replies_text)

                print(f"\n{'=' * 60}")
                print(f"貼文 {post_id}（本次輸入約 {len(full_context)} 字元）")
                print(f"{'=' * 60}")

                results = {}
                for model in MODELS_TO_COMPARE:
                    keywords = extract_specific_keywords(full_context, existing_keywords, model=model)
                    print(f"[{model}] → {keywords}")
                    results[model] = keywords

                save_comparison_file(post_id, text, replies_text, results)
    finally:
        conn.close()


if __name__ == "__main__":
    compare()