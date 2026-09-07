# threads-backup
[![Threads](https://img.shields.io/badge/Threads-@brownian.motion.99-000000?logo=Threads&logoColor=white)](https://www.threads.net/@brownian.motion.99)
[![Powered by AWS CloudFront](https://img.shields.io/badge/Powered%20by-AWS%20CloudFront-FF9900?logo=amazonaws&logoColor=white)](https://d3dqh426fzhnl5.cloudfront.net)

科學傳播系列《每天分享一個大氣科學知識直到我沒梗》的備份。

《每天分享一個大氣科學知識直到我沒梗》是本人於 2025 年底開始於 threads 日更的科學傳播短文系列，目前已累積超過 200 篇短文。由於貼文數量的增加，現在已經很難單純透過記憶來尋找過去的貼文，再加上 threads 的搜尋功能基本上可說是聊勝於無，本人便萌生自建資料庫與搜尋系統的想法。

這個 Repo 的主要目的為：
1. 備份 threads 貼文
2. 方便查詢過去的貼文
3. 學習使用 Postgres 建置關聯式資料庫
4. 學習使用 html、css、javascript 打造前端系統
5. 學習 Docker 與雲端平台部署

這是一份個人 side project，需要特定帳號的 threads api token，分類與標記系統也是為了大氣科學知識特別設計，非通用工具，因此這邊主要展示架構設計與實作過程。

## Features

- 透過 threads api 自動抓取貼文、回覆、圖片與影片
- 使用 LLM 自動分類貼文並標記關鍵字
- 透過標記與內文動態搜尋內容
- 透過前端網頁與資料庫進行交互

## Architecture

```mermaid
flowchart TD
    Browser["Browser<br/>HTML/CSS/JS frontend"]

    subgraph aws["AWS Cloud"]
        CFFrontend["CloudFront<br/>OAC → S3"]
        CFAPI["CloudFront<br/>API · Shield Standard"]
        ALB["ALB<br/>threads-backup-alb-sg · 443"]
        ECS["ECS Fargate task<br/>threads-backup-ecs-task-sg · 8000<br/>FastAPI"]
        RDS[("Aurora PostgreSQL Serverless v2<br/>threads-backup-rds-sg · 5432<br/>reader / writer 分離")]
        S3Media[("S3 media bucket<br/>public GetObject only")]
        S3Frontend[("S3 frontend bucket")]
        Secrets["Secrets Manager<br/>DB_READER_PASSWORD"]
    end

    subgraph local["本機環境（ingestion / tagging，規劃遷移雲端）"]
        Jobs["ingestion + tagging script<br/>手動觸發"]
    end

    ThreadsAPI["Threads API<br/>Fetches posts, media"]
    AnthropicAPI["Anthropic API<br/>Keyword tagging"]

    Browser -->|HTTP| CFFrontend
    CFFrontend --> S3Frontend
    Browser -->|HTTP| CFAPI
    CFAPI --> ALB
    ALB --> ECS
    ECS -->|queries| RDS
    ECS --> S3Media
    ECS -.->|GetSecretValue| Secrets

    Jobs -.->|暫時直連 5432| RDS
    Jobs -->|下載| S3Media
    ThreadsAPI --> Jobs
    AnthropicAPI --> Jobs

    classDef planned stroke-dasharray: 5 5
    class local,Jobs planned
```
這個服務由 frontend、api、db、jobs 四個部分組成：
- frontend：靜態網頁，透過 S3 + CloudFront（OAC）發佈
- api：ECS Fargate 上的 FastAPI，經 ALB／CloudFront 對外提供查詢與篩選功能，透過 Secrets Manager 取得資料庫密碼
- db：Aurora PostgreSQL Serverless v2，reader／writer 角色分離，儲存貼文、回覆、標記與圖片 id
- jobs：批次執行抓取、標記貼文工作，**目前仍在本機執行、透過固定 IP 直連 RDS**，為手動觸發，規劃遷移至雲端排程自動執行

```mermaid
flowchart LR
    subgraph ingest["擷取（本機，規劃遷移雲端）"]
        Threads["Threads 貼文<br/>brownian.motion.99"]
        Ingest["ingestion script<br/>呼叫 Threads API"]
        Media[("S3 media bucket<br/>圖片・影片縮圖")]
    end

    subgraph tag["標記（本機，規劃遷移雲端）"]
        Haiku["general tagging<br/>claude-haiku"]
        Sonnet["specific tagging<br/>claude-sonnet"]
        Review["human review<br/>手動合併同義詞"]
    end

    DB[("Aurora PostgreSQL<br/>posts / tags")]

    subgraph serve["查詢與顯示（AWS）"]
        API["FastAPI on ECS Fargate<br/>filter / search"]
        Frontend["S3 + CloudFront<br/>post list + detail"]
    end

    Threads --> Ingest
    Ingest -.->|暫時直連寫入| DB
    Ingest -->|上傳| Media
    DB --> Haiku
    Haiku -.->|寫入分類| DB
    DB --> Sonnet
    Sonnet -.->|寫入關鍵字| DB
    DB -.->|產生 markdown| Review
    Review -.->|人工套用| DB
    DB --> API
    Media --> API
    API --> Frontend

    classDef planned stroke-dasharray: 5 5
    class ingest,tag,Ingest,Haiku,Sonnet,Review planned
```
透過 threads api 自動抓取貼文後寫入資料庫，圖片與影片縮圖上傳至 S3 media bucket。透過 anthropic api 呼叫 claude-haiku 進行貼文分類、呼叫 claude-sonnet 生成關鍵字以標記貼文，LLM 生成之關鍵字需定期人工審核。ingestion 與 tagging 目前暫時在本機以固定 IP 直連 Aurora 執行（圖中虛線部分），查詢與顯示則已全面部署於 AWS（ECS Fargate + S3 + CloudFront）。

## Database

```mermaid
erDiagram
    posts ||--o{ replies : "root_post_id"
    posts ||--o{ images : "root_post_id"
    replies ||--o{ images : "root_reply_id"
    posts ||--o{ post_keywords : "post_id"
    keywords ||--o{ post_keywords : "keyword_id"

    posts {
        text id PK
        text text
        timestamptz timestamp
        text permalink
        text media_type
        boolean is_quote_post
    }

    replies {
        text id PK
        text root_post_id FK
        text text
        timestamptz timestamp
        text permalink
        text media_type
        boolean is_quote_post
    }

    images {
        text id PK
        text root_post_id FK
        text root_reply_id FK
        text local_path
    }

    keywords {
        int id PK
        text word UK
        text category
        boolean reviewed
    }

    post_keywords {
        text post_id PK_FK
        int keyword_id PK_FK
    }

```
- posts 儲存貼文主體。
- replies 儲存由 `@brownian.motion.99` 於貼文下方的回覆。
- images 儲存貼文或回覆附帶的圖片或影片，下載後存於 `local_path`。images 當中的一個物件同時只會對應到一則貼文或是一則回覆，其 root_post_id 與 root_reply_id 為彼此互斥的 foreign key。
- keywords 儲存貼文的關鍵字，keywords.word 具有 unique 限制，keywords.category 分為 general 與 specifc，general 作為貼文分類用，非必要不新增關鍵字；specific 則是由 LLM 根據貼文自動生成，需定期手動審核。
- post_keywords 為貼文與關鍵字的 junction table。

## Tech Stacks
- Framework: Python 3.12, FastAPI, vanilla JS
- Database: Aurora PostgreSQL Serverless v2 (`psycopg3`)
- Containerization: Docker (multi-arch build for Fargate), ECR
- Cloud infra: ECS Fargate (Express Mode), ALB, CloudFront + S3 (frontend), S3 (media), Secrets Manager, CloudWatch Logs
- Fetching posts with threads api
- Categorizing posts wtih `claude-haiku`, extracting keywords from posts with `claude-sonnet`

## Demo
> ![homepage](.github/screenshots/homepage.png)
> 貼文列表頁


> ![filtering](.github/screenshots/filtering.png)
> 可透過勾選關鍵字來篩選貼文


> ![searching](.github/screenshots/searching.png)
> 可透過文字搜尋貼文

> ![post](.github/screenshots/post.png)
> 模仿 threads 的貼文顯示介面