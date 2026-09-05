import os
from dotenv import load_dotenv
from anthropic import Anthropic
from common.tagging_runner import run_tagging_job
from common.db import get_connection, get_or_create_keyword_id

load_dotenv()

client = Anthropic()  # 自動讀取 ANTHROPIC_API_KEY

GENERAL_TAGGER_MODEL = os.environ.get("GENERAL_TAGGER_MODEL", "claude-haiku-4-5-20251001")

GENERAL_KEYWORDS = [
    "停更",
    "大氣動力學", "地物流力", "全球大氣環流", "資料同化",
    "大氣熱力學", "雲物理學", "雲動力學", "雲與環境",
    "天氣學", "數值天氣預報",
    "氣候學", "氣候變遷",
    "大氣輻射學", "大氣遙測",
    "大氣化學", "大氣物理化學", "生地化循環", "生物氣象學", "陸地大氣交互作用",
    "大氣測計學",
    "應用數學", "統計", "海洋大氣交互作用",
]

TOOL_DEF = {
    "name": "tag_keywords",
    "description": "標記這篇貼文符合的 general 關鍵字",
    "input_schema": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string", "enum": GENERAL_KEYWORDS},
                "description": "符合的關鍵字，最多 3 個，若都不符合則為空陣列",
            }
        },
        "required": ["keywords"],
        "additionalProperties": False,
    },
    "strict": True,
}


def classify_post(post_text: str) -> list[str]:
    response = client.messages.create(
        model=GENERAL_TAGGER_MODEL,
        max_tokens=200,
        tools=[TOOL_DEF],
        tool_choice={"type": "tool", "name": "tag_keywords"},
        messages=[{
            "role": "user",
            "content": f"""這是一篇大氣科學相關的 Threads 貼文：

{post_text}

請標記符合的關鍵字，最多 3 個。

「停更」的判斷標準（請嚴格遵守，不要輕易使用）：
只有當貼文明確表示作者當天沒有準備知識性內容，例如直接說偷懶、沒梗、跳過今天、去開會、處理雜事、身體不適等，才標記「停更」。
只要貼文有嘗試傳達任何科學概念、方法論、工具介紹或個人觀察與心得（即使很簡短、即使用玩笑或自嘲的語氣包裝、即使標題看起來像在鬧），都不算停更，請正常依內容判斷學科分類。
不要因為貼文篇幅短、語氣輕鬆、或包含玩笑收尾，就判斷為停更。""",
        }],
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    keywords = tool_use_block.input["keywords"]

    invalid = [k for k in keywords if k not in GENERAL_KEYWORDS]
    if invalid:
        print(f"  [警告] 模型回傳了清單外的關鍵字，已過濾：{invalid}")
    valid_keywords = [k for k in keywords if k in GENERAL_KEYWORDS]

    if len(valid_keywords) > 3:
        print(f"  [警告] 模型回傳超過 3 個關鍵字，已截斷：{valid_keywords}")
        valid_keywords = valid_keywords[:3]

    return valid_keywords


def fetch_posts_needing_general_tags(cur, limit: int | None = None):
    query = """
        SELECT p.id, p.text
        FROM posts p
        WHERE NOT EXISTS (
            SELECT 1 FROM post_keywords pk
            JOIN keywords k ON pk.keyword_id = k.id
            WHERE pk.post_id = p.id AND k.category = 'general'
        )
        AND p.text IS NOT NULL
    """
    if limit is not None:
        query += " LIMIT %s"
        cur.execute(query, (limit,))
    else:
        cur.execute(query)
    return cur.fetchall()


def tag_general_keywords_for_post(cur, post_id: str, post_text: str):
    keywords = classify_post(post_text)
    for word in keywords:
        keyword_id = get_or_create_keyword_id(cur, word, category="general")
        cur.execute(
            """
            INSERT INTO post_keywords (post_id, keyword_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (post_id, keyword_id),
        )
    return keywords


def main(limit: int | None = None):
    run_tagging_job(fetch_posts_needing_general_tags, tag_general_keywords_for_post, limit=limit)


if __name__ == "__main__":
    main()