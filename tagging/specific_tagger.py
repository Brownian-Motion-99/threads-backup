import os
from dotenv import load_dotenv
from anthropic import Anthropic

from common.db import get_connection, get_or_create_keyword_id
from common.tagging_runner import run_tagging_job

load_dotenv()

client = Anthropic()

SPECIFIC_TAGGER_MODEL = os.environ.get("SPECIFIC_TAGGER_MODEL", "claude-haiku-4-5-20251001")

TOOL_DEF = {
    "name": "extract_specific_keywords",
    "description": "從貼文中萃取細節領域關鍵字（專有名詞、理論、機制等）",
    "input_schema": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
                "description": "細節關鍵字，跟隨貼文原文使用的語言，若都不適用則為空陣列",
            }
        },
        "required": ["keywords"],
    },
}


def get_existing_specific_keywords(cur) -> list[str]:
    cur.execute("SELECT word FROM keywords WHERE category = 'specific' ORDER BY word")
    return [row[0] for row in cur.fetchall()]


def build_full_context(post_text: str, replies_text: str | None) -> str:
    if not replies_text:
        return post_text
    return f"{post_text}\n\n以下是這篇貼文底下的回覆內容（可能包含參考資料 reference）：\n{replies_text}"


def extract_specific_keywords(full_context: str, existing_keywords: list[str], model: str = SPECIFIC_TAGGER_MODEL) -> list[str]:
    existing_list_str = "、".join(existing_keywords) if existing_keywords else "（目前尚無）"

    response = client.messages.create(
        model=model,
        max_tokens=300,
        tools=[TOOL_DEF],
        tool_choice={"type": "tool", "name": "extract_specific_keywords"},
        messages=[{
            "role": "user",
            "content": f"""這是一篇大氣科學相關的 Threads 貼文，以及底下的回覆內容（回覆中常會附上參考資料 reference，例如論文、書籍或報告名稱）：

{full_context}

請萃取這篇貼文（含回覆中的 reference）中出現的細節領域關鍵字（例如具體的理論、機制、專有名詞），最多 5 個。
規則：
1. 貼文開頭第一段的引文當中有時會有與貼文主旨無關的資訊，那些不該被作為判斷，舉例來說：
   古氣候的資料一般是透過地層、冰芯和氧同位素等途徑取得，但這些資料通常有空間解析度和覆蓋率的問題，因此比較另類的作法就是從古代文獻中尋找天氣紀錄。
   REACHES（Reconstructed East Asian Climate Historical Encoded Series）是由中研院根據《中國三千年氣象記錄總集》整理得到的數位化古中國氣象紀錄，其中包括了降水、乾旱、洪水等被史官紀錄下來的天氣事件。資料來源十分廣泛，從太史、欽天監、各類實錄等中央歷史檔案，到各州縣的地方志都包含在其中，這讓我們可以在缺乏現代觀測資料的條件之下一定程度地了解古代東亞的氣候特徵。
   不過不難想像的是，這些資料有非常大的侷限性，例如空間的分布不均，因為在古代只有東部有較多的人口與完整的官僚體系；時間上的連續性與覆蓋率也有問題，長江與黃河流域周圍的城市有比較多的資料，反之則通常只有寥寥數筆，這是使用這些資料時需要額外注意的部分。
   這則貼文中的地層、冰芯、氧同位素不是貼文的重點，這些不該被當作關鍵字。
2. 關鍵字語言請跟隨原文使用的語言；如果同一個概念在這篇貼文中同時以中英文出現，請採用該貼文中出現次數較多的那個語言形式作為關鍵字，不要用「中文 (英文)」這種中英混合的寫法。
3. 資料庫中已經存在以下關鍵字：{existing_list_str}
   如果提到的概念跟上述清單語意相符，請直接重用清單中的字，不要創造新的同義詞。
4. 不要標記已經算是廣泛學科分類的詞（例如「氣候學」「雲物理學」這種課程層級的詞），只標記更細節、更具體的概念。
5. 只萃取貼文核心討論的科學機制或專有名詞，不要把論文的應用情境、延伸結論當作關鍵字（例如貼文核心是在講 isoprene 排放機制，就不要標「urban greening」這種偏向研究情境的詞）。
6. 若沒有明顯的細節專有名詞，回傳空陣列即可。""",
        }],
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return tool_use_block.input["keywords"]


def fetch_posts_needing_specific_tags(cur, limit: int | None = None):
    query = """
        SELECT
            p.id,
            p.text,
            string_agg(r.text, E'\n---\n' ORDER BY r."timestamp") AS replies_text
        FROM posts p
        LEFT JOIN replies r ON r.root_post_id = p.id
        WHERE NOT EXISTS (
            SELECT 1 FROM post_keywords pk
            JOIN keywords k ON pk.keyword_id = k.id
            WHERE pk.post_id = p.id AND k.category = 'specific'
        )
        AND p.text IS NOT NULL
        GROUP BY p.id, p.text
    """
    if limit is not None:
        query += " LIMIT %s"
        cur.execute(query, (limit,))
    else:
        cur.execute(query)
    return cur.fetchall()


def tag_specific_keywords_for_post(cur, post_id: str, post_text: str, replies_text: str | None):
    existing_keywords = get_existing_specific_keywords(cur)
    full_context = build_full_context(post_text, replies_text)
    keywords = extract_specific_keywords(full_context, existing_keywords)

    for word in keywords:
        keyword_id = get_or_create_keyword_id(cur, word, category="specific")
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
    run_tagging_job(fetch_posts_needing_specific_tags, tag_specific_keywords_for_post, limit=limit)


if __name__ == "__main__":
    main()