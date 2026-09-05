from common.db import get_connection

TEMPLATE_PATH = "tagging/keyword_update_template.md"


def fetch_all_specific_keywords(cur) -> list[str]:
    cur.execute("""
        SELECT k.word
        FROM keywords k
        WHERE k.category = 'specific' AND k.reviewed = FALSE
        ORDER BY k.word
    """)
    return [row[0] for row in cur.fetchall()]


def generate_template():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            words = fetch_all_specific_keywords(cur)
    finally:
        conn.close()

    lines = ["# Specific 關鍵字更新對照表", "", "| 原有 | 更新 |", "|------|------|"]
    for word in words:
        lines.append(f"| {word} | {word} |")  # 右欄預設跟左欄一樣，你只需要改想調整的那幾行

    with open(TEMPLATE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"已產生 {len(words)} 筆關鍵字模板：{TEMPLATE_PATH}")


if __name__ == "__main__":
    generate_template()