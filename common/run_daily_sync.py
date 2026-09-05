from ingestion.import_posts import main as import_main
from tagging.general_tagger import main as general_tag_main
from tagging.specific_tagger import main as specific_tag_main

def main():
    
    print("=== 開始匯入新貼文 ===")
    import_main()

    print("=== 開始一般關鍵字標記 ===")
    general_tag_main()

    print("=== 開始特定關鍵字標記 ===")
    specific_tag_main()

    print("=== 全部完成 ===")


if __name__ == "__main__":
    main()