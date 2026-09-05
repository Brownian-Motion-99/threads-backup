from common.db import get_connection, merge_keywords, delete_keyword, mark_as_reviewed

TEMPLATE_PATH = "tagging/keyword_update_template.md"


def parse_template(path: str) -> list[tuple[str, str]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != 2:
                continue
            original, updated = cells
            if original == "原有" or set(original) == {"-"}:
                continue
            rows.append((original, updated))
    return rows


def apply_updates(path: str = TEMPLATE_PATH):
    rows = parse_template(path)

    to_delete = [o for o, u in rows if u == ""]
    to_merge = [(o, u) for o, u in rows if u and u != o]
    unchanged = [o for o, u in rows if u == o]

    print(f"共 {len(rows)} 筆：{len(to_merge)} 筆更新／合併、{len(to_delete)} 筆刪除、{len(unchanged)} 筆不變")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for original, updated in to_merge:
                merge_keywords(cur, original, updated, category="specific")
            for original in to_delete:
                delete_keyword(cur, original, category="specific")
                print(f"  已刪除 '{original}'")

            # 這批全部處理完，最終保留下來的字（更新後的名稱 + 沒變動的字）都標記為已審核
            final_words = list({u for o, u in to_merge} | set(unchanged))
            mark_as_reviewed(cur, final_words, category="specific")

            conn.commit()
    finally:
        conn.close()
    print("更新完成")


if __name__ == "__main__":
    apply_updates()