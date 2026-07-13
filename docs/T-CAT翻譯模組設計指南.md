# T-CAT 翻譯模組設計指南（v2 — Supabase 架構版）

> 本文件以現有 T-CAT Buddhist Vocabulary Tool（PROGRESS.md 2026-06 快照）為基準，
> 涵蓋兩件事：**(A) 資料層遷移 — Google Sheets → Supabase Postgres（T0 階段）**，
> **(B) 新增「中翻英人機協作翻譯模組」**。
>
> v2 關鍵決策：Supabase 為唯一資料庫；Google Sheets 完全退役；
> 所有資料修改僅透過 T-CAT 介面，團隊成員不直接存取資料庫。
>
> **進度同步（2026-07-12，依 PROGRESS.md）**：T0～T3 已完成（T3 為 MVP），
> T2.1（句群拆分審閱工作區）已完成並補入路線圖。詳見第七部分「實際實作對照」
> 與第十部分路線圖表格的狀態欄。

---

## 第一部分：架構決策摘要

| 決策 | 內容 | 理由 |
|---|---|---|
| 資料庫 | **Supabase（託管 Postgres）** | pgvector 內建（RAG 一步到位）、Table Editor 供管理者查看、pgBouncer 連線池適配 CGI 短命連線 |
| Google Sheets | **完全退役**，遷移後匯出最終 CSV 存檔 | 團隊不需直接改資料；備份改用自動化匯出 |
| 資料存取原則 | 只有伺服器端持有 Supabase 金鑰（`.env`）；成員一律透過 T-CAT 介面操作 | 應用層統一權限控管，杜絕誤改資料風險 |
| 備份策略 | GitHub Actions 每週排程匯出（pg_dump 或逐表 CSV）存入私有 repo | 取代 Sheets 的備份角色，可還原、可追溯 |
| 不動的部分 | Flask + CGI + GreenGeeks、Google OAuth（Authlib）、前端 vanilla JS、CI/CD 管線 | 一次只改一層，控制風險 |
| Python 套件 | `gspread` → `psycopg2-binary`（或 supabase-py） | 連線字串使用 pgBouncer transaction mode 端口 |

> **CGI 與連線池**：CGI 每個請求都是新行程、新資料庫連線。必須使用 Supabase
> 提供的 **pooled connection string（pgBouncer, transaction mode, 端口 6543）**，
> 而非直連端口 5432，否則連線數會被快速耗盡。

---

## 第二部分：T0 — 資料遷移階段（排在所有翻譯模組工作之前）

| 子階段 | 內容 | 驗收標準 |
|---|---|---|
| **T0-1 建 Schema** | 在 Supabase 建立既有六表 + 翻譯模組五表（DDL 見附錄），含索引、外鍵、約束 | 全部資料表建立完成，約束生效 |
| **T0-2 遷移腳本** | 一次性 Python 腳本：gspread 讀出 → 清洗（日期字串→timestamptz、空值正規化、角色/狀態值正規化）→ 寫入 Postgres | 逐表筆數比對一致；抽樣 20 筆逐欄比對無誤 |
| **T0-3 改寫資料層** | `sheets.py` → `db.py`，**函式簽名保持不變**，routes 層近乎零修改 | 本機全功能回歸測試通過（詞彙 CRUD、Extraction 全流程、審計日誌） |
| **T0-4 切換上線** | 選無人作業時段：凍結 Sheets 寫入 → 最終遷移 → 部署 → 線上驗證 | 生產環境全功能正常；Audit_Log 正常寫入 |
| **T0-5 收尾** | Sheets 匯出最終 CSV 存檔後停用；建立每週自動備份排程；`.env` 移除 Sheets 相關變數、加入 `DATABASE_URL` | 備份排程成功跑過一輪；credentials.json 從伺服器移除 |

**遷移對照**：

| 原工作表 | 新資料表 | 備註 |
|---|---|---|
| Terms | `terms` | 26 欄照搬；日期改 timestamptz；status/category 加約束 |
| Members | `members` | email 設 UNIQUE |
| Sources | `sources` | — |
| Audit_Log | `audit_log` | `term_id` 保留字串型（歷史紀錄含已刪詞條，不設外鍵） |
| ExtractionDocuments | `ext_documents` | — |
| ExtractionParagraphs | `ext_paragraphs` | 加 `(document_id, paragraph_index)` 複合索引 |
| Votes | **不遷移** | Stage 3 已棄用；匯出 CSV 存檔留念 |

**ID 策略**：`T000001` / `D000001` 顯示格式保留（前端與審計日誌已依賴），
資料庫內部另設 `id bigint generated always as identity` 主鍵做外鍵關聯；
顯示 ID 存於 `display_id` 欄位並設 UNIQUE。新流水號由 Postgres sequence 產生，
徹底解決 Sheets 時代「掃全表找最大 ID」的競態問題。

---

## 第三部分：可複用的既有資產（翻譯模組地基）

| 既有資產 | 在翻譯模組中的用途 |
|---|---|
| **terms 表**（Final、TranslationKnown） | 術語約束：翻譯 prompt 注入固定譯法 |
| **Extraction 上傳管線** | 編碼偵測（UTF-8 → GB18030 → Big5）、空行分段邏輯直接沿用 |
| **`ai.py`** | 新增 `translate_unit()` 沿用同一封裝與錯誤處理模式 |
| **角色權限**（viewer→admin 五級） | 直接映射，不新增角色 |
| **audit_log + `write_audit()`** | 所有翻譯修訂寫入同一審計機制 |
| **兩層 Tab UI** | 新增第三個頂層 Tab：**Translation** |
| **Picker / Working 雙子視圖** | 翻譯模組沿用「選書 → 工作區」導覽 |
| **術語高亮**（greedy longest-match-first） | 翻譯工作區中文面板直接複用 |
| **候選詞 modal** | 翻譯中選詞入庫，與詞彙模組互相導流 |

---

## 第四部分：翻譯模組資料模型（五張新表）

> 有了真正的關聯式資料庫，v1 裡遷就 Sheets 的設計（小數 UnitIndex、不刪列標記）
> 全部改為正規做法。

### `trans_books`（書籍）
- `id`、`display_id`（B000001）、`title`、`source_id → sources`、
  `created_by`、`created_at`、`status`（active/archived）

### `trans_chapters`（章節）
- `id`、`display_id`（C000001）、`book_id → trans_books`、`chapter_index`、
  `title`、`section_type`（**body/editorial/preface/postscript** — 本社按等按語單獨標記）、
  `claimed_by`（認領者 email，NULL = 未認領）、
  `status`（not_started/in_progress/in_review/completed）

### `trans_units`（翻譯單元 — 核心表）
- `id`、`display_id`（U000001）、`chapter_id → trans_chapters`、
  `paragraph_index`、`unit_order`（**numeric 型別** — 拆句插入用平均值定序，正規的 fractional indexing）
- `chinese_text`、`english_draft`（AI 初譯，永不覆蓋）、`english_final`（目前定稿）
- `split_map jsonb`（AI 拆句對照：`[{zh, en}]`，長句一對多對齊）
- `status`（untranslated/ai_drafted/in_review/revised/approved）
- `is_long_sentence boolean`（逗號+頓號+分號 > 3 或字數 > 45）
- `ai_model text`（產生初譯的模型，供品質分組比較）
- `translated_by`、`reviewed_by`、`approved_by`、`last_modified_by`、`last_modified_at`
- 拆分/合併：真正的 INSERT / UPDATE 操作 + audit_log 記錄 `unit_split` / `unit_merge`；
  被合併的單元以 `merged_into → trans_units.id` 標記（保留紀錄但查詢時過濾）

### `trans_revisions`（修訂歷史 — 閉環反饋語料庫，只追加不修改）
- `id`、`display_id`（R000001）、`unit_id → trans_units`
- `chinese_text`（冗餘快照，防原文後續拆併對不上）
- `english_before`、`english_after`
- `revision_type`（terminology/tone/grammar/split/other）
- `note`（譯者「為什麼這樣改」）
- `revised_by`、`revised_at`
- `embedding vector(1536)` — **pgvector 欄位**，寫入時同步計算中文原文的 embedding

### `style_guide`（風格指南 — 結構化規則）
- `id`、`display_id`（S000001）、`category`（敬語/專有名詞格式/長句拆分/語氣/其他）
- `rule_text`（英文書寫，直接注入 prompt）
- `example_before`、`example_after`
- `active boolean`（停用不刪除）
- `source_revision_ids bigint[]`（歸納自哪些修訂，可追溯）
- `created_by`（限 Leader/Admin）、`created_at`

---

## 第五部分：中文分句實作規格（`segmenter.py`）

### 匯入流程
1. 上傳中文 .txt（沿用編碼偵測：UTF-8 → GB18030 → Big5）
2. 空行分段（與 Extraction 相同）
3. 段首偵測 `section_type`：「本社按」「譯者序」「編者按」「跋」等開頭自動標記
4. 段內分句 → 寫入 `trans_units`（單一 transaction 批次 INSERT）

### 分句演算法
```
硬邊界（切分點）：。 ！ ？ ……（含全形省略號）
引號保護：「」『』“” 內部的終結符號一律不切分
　　　　　（掃描時維護引號深度計數器，深度 > 0 時忽略終結符）
收尾規則：終結符後緊跟的引號收尾（如 。」）歸入前一句
長句標記：逗號+頓號+分號總數 > 3 或字數 > 45 → is_long_sentence = TRUE
```

### 標準測試案例（實作驗收門檻）
```
輸入：處處都對眾生說：「我是一個普通人，是與你們一樣平等的。」帕母儘管
　　　如此態度，但是我們和高僧們認為她就是當今在世真正的佛菩薩。
正確：整段為【一個】翻譯單元（引號內句號不切分）
錯誤：在「平等的。」處切成兩句 → 測試失敗
```
排比長句測試：「自由女神像的消失是神秘的，……」整段一個句號
→ 應為一個單元 + is_long_sentence 標記。

---

## 第六部分：AI 翻譯管線（閉環核心）

### Prompt 組裝（`ai.py` 新函式 `translate_unit()`）
```
┌─ 1. 系統指令：譯者角色（佛法文本、目標讀者、整體語域）
├─ 2. 風格指南：style_guide 中 active=TRUE 的規則
├─ 3. 術語約束：本句命中的 terms（Final/TranslationKnown 非空）
│　　　→「下列術語必須使用固定譯法：涅槃→Nirvana, …」
├─ 4. 相似範例：pgvector 檢索 trans_revisions 最相似 3-5 筆
│　　　（原文 → 人工定稿，few-shot 格式）
└─ 5. 待譯句 + 前後各一句上下文
```
長句（is_long_sentence）額外要求回傳 split_map：
「標注你將此中文長句拆成幾個英文句子、各對應中文哪一段」。

### 範例檢索 — pgvector 直接實作（v1 兩階段方案作廢）
```sql
SELECT chinese_text, english_after
FROM trans_revisions
ORDER BY embedding <=> :query_embedding
LIMIT 5;
```
- 寫入修訂時同步計算並存入 embedding（一次計算永久使用）
- 語料 < 數萬筆不需要建 ivfflat/hnsw 索引，順序掃描已足夠快
- 冷啟動期（修訂 < 50 筆）：檢索結果可能不夠相似，prompt 組裝時
  設相似度門檻，不夠相似就不注入範例（避免誤導），僅靠風格指南+術語約束

### 反饋寫入時機
| 譯者操作 | 系統行為 |
|---|---|
| **批准**（未修改） | status → approved；不寫 revisions |
| **修改後批准** | status → revised；寫入 trans_revisions（before/after + 類別 + 備註 + embedding） |
| **重新生成** | 以最新指南+術語+範例重跑；english_draft 保留，新結果進 english_final 供比對 |

---

## 第七部分：API 端點（routes/translate.py 新 blueprint）

| 端點 | 方法 | 權限 | 功能 |
|---|---|---|---|
| `/api/trans/books` | POST | member+ | 上傳中文書 → 分段分句 → 建 book/chapters/units |
| `/api/trans/books` | GET | login | 書單（含各章進度統計，一句 SQL GROUP BY 完成） |
| `/api/trans/chapters/<id>/units` | GET | login | 章節內全部單元 |
| `/api/trans/chapters/<id>/claim` | PATCH | member+ | 認領 / 釋放章節 |
| `/api/trans/units/<id>/translate` | POST | member+ | 觸發 AI 翻譯 |
| `/api/trans/units/<id>` | PATCH | member+ | 保存修訂（transaction 內同時寫 revisions） |
| `/api/trans/units/<id>/approve` | PATCH | leader+ | 批准定稿 |
| `/api/trans/units/<id>/split` | POST | member+ | 拆分單元 |
| `/api/trans/units/merge` | POST | member+ | 合併相鄰單元 |
| `/api/trans/styleguide` | GET/POST/PATCH | 寫入 leader+ | 風格指南 CRUD |

**批次翻譯**：CGI 無背景任務，整段/整章批次翻譯由**前端逐句驅動**
（每句一個請求 + 進度條），嚴禁單一請求內迴圈呼叫 AI（必逾時）。

### 實際實作對照（依 PROGRESS.md 2026-07-12，取代上表 T2/T2.1/T3 部分）

實作過程中發現整章一次匯入＋AI逐句翻譯會導致 CGI 逾時，改為「匯入只做純演算法分句、AI 分組與翻譯由前端逐段/逐句觸發」的兩段式流程，並新增 T2.1 草稿審閱層。實際端點：

| 端點 | 方法 | 權限 | 對應設計 |
|---|---|---|---|
| `/api/trans/books` | POST（JSON，僅 title） | member+ | 原設計含檔案上傳一次建全書；改為先建書（純 metadata），章節另外上傳 |
| `/api/trans/books/<id>/chapters` | POST（檔案上傳） | admin | 新增：上傳 .txt → 分段+分句（純演算法，無 AI）→ 建 `trans_unit_drafts` |
| `/api/trans/books` | GET | login | 同設計，改呼叫 `list_trans_books()` RPC |
| `/api/trans/books/<id>/chapters` | GET | login | 新增：章節列表 |
| `/api/trans/chapters/<id>/drafts` | GET | login | 新增（T2.1）：段落草稿列表 |
| `/api/trans/chapters/<id>/paragraphs/<idx>/group-preview` | POST | member+ | 新增（T2.1）：單段 AI 主題分組 |
| `/api/trans/chapters/<id>/paragraphs/<idx>/draft` | PATCH | member+ | 新增（T2.1）：人工調整拖曳分組，自動存檔 |
| `/api/trans/chapters/<id>/paragraphs/<idx>/confirm` | POST | member+ | 新增（T2.1）：確認寫入 `trans_units`（刪舊插新，可重跑） |
| `/api/trans/chapters/<id>/units` | GET | login | 同設計 |
| `/api/trans/units/<id>/translate` | POST | member+ | 對應設計「觸發 AI 翻譯」；首次寫 `english_draft`+`english_final`，重譯只覆蓋 `english_final` |
| `/api/trans/units/<id>` | PATCH（body 含 `approve`） | member+／approve 需 leader+ | 合併設計中「保存修訂」與「批准定稿」為單一端點，以 `approve` 布林區分 |
| `/api/trans/known-terms` | GET | login | 新增：術語高亮＋候選詞 modal 用（沿用 Extraction 模組機制） |

**尚未實作**（列於設計但實際未建，非遺漏，屬 T4/T5 範圍）：`/api/trans/chapters/<id>/claim`（章節認領）、
`/api/trans/units/<id>/split`、`/api/trans/units/merge`、`/api/trans/styleguide` CRUD、pgvector 範例檢索、
三欄式工作區（左章節樹／中卡片／右參考面板）與 diff 高亮。目前 UI 為「段落卡片 + 逐句列表」的簡化版工作區。

---

## 第八部分：UI — Translation 頂層 Tab

### 導覽（沿用 Picker/Working 模式）
- **Picker**：書單（進度條 + 各章狀態色標）＋ 上傳新書表單
- **Working**：三欄式工作區

```
┌──────────┬──────────────────────────────┬──────────────┐
│ 左欄      │ 中欄（主工作區）                │ 右欄          │
│ 章節導覽樹 │ 逐句對照卡片                    │ 參考面板       │
│ ├ 進度色標 │ ┌────────────────────────┐  │ ├ 命中術語     │
│ ├ 認領狀態 │ │ 中文原句（術語高亮·複用）   │  │ ├ 相似歷史譯例  │
│ └ 章節跳轉 │ │ 英譯（可編輯，diff 高亮）  │  │ └ 本句批註討論  │
│           │ │ [批准][修改後批准][重譯]   │  │              │
│           │ └────────────────────────┘  │              │
└──────────┴──────────────────────────────┴──────────────┘
```
- 中文面板複用 `extHighlightKnownTerms()`（藍 = 已有定譯、金 = 無定譯）
- 點高亮術語 → 開啟既有候選詞 modal → 翻譯與詞庫互相導流
- 長句卡片展開 split_map「AI 拆句對照」+「接受拆分 / 調整」
- diff：english_draft vs english_final 字詞級差異標色（前端純 JS）

### 狀態色標
灰 untranslated ／ 藍 ai_drafted ／ 金 in_review ／ 橙 revised ／ 綠 approved

---

## 第九部分：權限映射（不新增角色）

| 角色 | 翻譯模組能力 |
|---|---|
| Viewer | 唯讀瀏覽 |
| Depositor | 同 Viewer |
| Member | 認領章節、AI 翻譯、修訂、拆併句、批註 |
| Leader | Member + 批准定稿 + 風格指南管理 + 仲裁 |
| Admin | Leader + 上傳/封存書籍 |

資料庫層面：**唯一憑證是伺服器 `.env` 中的連線字串**；
不開放任何成員直接存取 Supabase；Supabase Dashboard 僅專案擁有者（你）持有。

---

## 第十部分：整體路線圖

| 階段 | 狀態（2026-07-12） | 內容 | 驗收標準 |
|---|---|---|---|
| **T0 資料遷移** | ✅ 完成 | Sheets → Supabase（見第二部分五個子階段） | 全功能回歸通過；備份排程運轉 |
| **T1 翻譯資料層** | ✅ 完成 | 五張新表 + `segmenter.py` | 引號保護測試案例通過（15 pytest 全過） |
| **T2 匯入+瀏覽** | ✅ 完成 | 上傳書籍 + Picker 書單 + 唯讀句列表；admin-only 存取旗標 | 整本書可上傳、逐章瀏覽 |
| **T2.1 草稿審閱**（新增階段，原路線圖未列） | ✅ 完成 | `sentence_map` 欄位＋`trans_unit_drafts` 表；分句→AI 主題分組→拖曳人工調整→自動存檔→確認寫入 `trans_units` | E2E SQL 流程驗證通過 |
| **T3 AI 預譯** | ✅ 完成（MVP） | `translate_unit()`（系統指令+術語約束）+ 編輯保存/批准端點 | 譯文含正確術語；修訂入庫；**尚未做本機端對端即時測試**（見 Next Steps） |
| **T4.1 Style Guide** | ✅ 完成 | `style_guide` CRUD（leader+ 寫入）+ prompt 注入 `translate_unit()` + 管理畫面 | 端點權限測試通過；**尚未實際新增規則做端對端測試** |
| **T4.2 雙供應商 Embedding + RAG** | ✅ 完成 | migration 010：`embedding_voyage`/`embedding_openai` 雙欄位 + 兩支 `find_similar_revisions_*` RPC；`embeddings.py`；相似度門檻 0.5；比較腳本 `compare_embedding_providers.py` | migration 驗收測試通過、RPC 已於 Supabase 驗證存在；**`trans_revisions` 尚無任何一筆有 embedding 資料**，RAG 注入與比較腳本都還沒跑過真實資料 |
| **T4.3 工作區與 diff** | ⏳ 規劃中 | 三欄式工作區（章節樹／卡片／參考面板）、diff 高亮（english_draft vs english_final） | 待 T4.1/T4.2 完成即時測試後排入 |
| **T5 協作** | ⏳ 規劃中 | 認領、批准流、批註 | 兩人同時作業不衝突 |
| **T6 品質追蹤** | ⏳ 規劃中 | 「人工修改幅度」趨勢儀表板（按模型分組） | 可視化修改幅度隨時間變化 |

> 相比 v1 路線圖：原 T6「SQLite 向量副本」作廢——pgvector 讓 RAG 提前到 T4
> 一步到位，品質追蹤升為 T6 主體。

---

## 第十一部分：風險與注意事項

1. **連線方式**：務必用 pgBouncer pooled 連線字串（端口 6543，transaction mode）。
   CGI 每請求新連線，直連 5432 會耗盡連線數。
2. **CGI 逾時**：批次 AI 翻譯由前端逐句驅動（第七部分）。
3. **模型選擇**：初譯可續用 Haiku；長句與重譯升級 Sonnet 級——`ai.py` 做成
   可配置，記錄於 `trans_units.ai_model`，T6 按模型分組比較品質。
4. **備份**：GitHub Actions 每週 pg_dump（Supabase 免費層本身也有每日備份，
   但自己再留一份異地備份成本極低）。`trans_revisions` 是未來微調語料，最有價值。
5. **Supabase 免費層休眠**：免費專案閒置 7 天會暫停，需手動喚醒。團隊每週
   都有人使用即不受影響；若在意可升級 Pro 或用備份排程順便「保活」。
6. **Node.js 24 升級**（既有待辦）：2026-09-16 前更新 deploy action。

---

## 附錄：Postgres Schema DDL（T0-1 執行用）

```sql
-- 啟用 pgvector
create extension if not exists vector;

-- ============ 既有系統六表 ============

create table members (
  id bigint generated always as identity primary key,
  email text not null unique,
  role text not null check (role in ('viewer','depositor','member','leader','admin')),
  name text, short_name text,
  added_by text, added_at timestamptz default now()
);

create table sources (
  id bigint generated always as identity primary key,
  display_id text unique,          -- 原 SourceID
  source_name text not null,
  source_type text, notes text
);

create table terms (
  id bigint generated always as identity primary key,
  display_id text unique not null, -- T000001
  chinese text not null,
  pinyin text, pali text, sanskrit text,
  context text, category text, notes text,
  translation1 text, translation2 text, translation3 text,
  translation_first text, translation_second text,
  translation_other1 text, translation_other2 text,
  translation_known text,
  final text,
  status text default 'pending' check (status in ('pending','finalized')),
  source text,
  romanization_plain text,
  source_content_chinese text, source_content_english text,
  added_by text, added_at timestamptz default now(),
  last_modified_by text, last_modified_at timestamptz
);
create index idx_terms_chinese on terms (chinese);
create index idx_terms_status on terms (status);

create table audit_log (
  id bigint generated always as identity primary key,
  ts timestamptz default now(),
  term_id text,                    -- 字串型，歷史紀錄含已刪詞條，不設外鍵
  term_chinese text,
  user_email text, user_name text,
  action_type text, field_changed text,
  old_value text, new_value text, details text
);
create index idx_audit_ts on audit_log (ts desc);

create table ext_documents (
  id bigint generated always as identity primary key,
  display_id text unique not null, -- D000001
  title text not null, source_name text,
  paragraph_count int,
  uploaded_by text, uploaded_at timestamptz default now(),
  last_viewed_index int default 0,
  status text default 'active'
);

create table ext_paragraphs (
  id bigint generated always as identity primary key,
  document_id bigint not null references ext_documents(id),
  paragraph_index int not null,
  chinese_text text, english_text text,
  unique (document_id, paragraph_index)
);

-- ============ 翻譯模組五表 ============

create table trans_books (
  id bigint generated always as identity primary key,
  display_id text unique not null, -- B000001
  title text not null,
  source_id bigint references sources(id),
  created_by text, created_at timestamptz default now(),
  status text default 'active' check (status in ('active','archived'))
);

create table trans_chapters (
  id bigint generated always as identity primary key,
  display_id text unique not null, -- C000001
  book_id bigint not null references trans_books(id),
  chapter_index int not null,
  title text,
  section_type text default 'body'
    check (section_type in ('body','editorial','preface','postscript')),
  claimed_by text,
  status text default 'not_started'
    check (status in ('not_started','in_progress','in_review','completed')),
  unique (book_id, chapter_index)
);

create table trans_units (
  id bigint generated always as identity primary key,
  display_id text unique not null, -- U000001
  chapter_id bigint not null references trans_chapters(id),
  paragraph_index int not null,
  unit_order numeric not null,     -- fractional indexing，拆句插入取平均
  chinese_text text not null,
  english_draft text,              -- AI 初譯，永不覆蓋
  english_final text,              -- 目前定稿
  split_map jsonb,                 -- [{zh, en}] 長句拆分對照
  status text default 'untranslated'
    check (status in ('untranslated','ai_drafted','in_review','revised','approved')),
  is_long_sentence boolean default false,
  ai_model text,
  merged_into bigint references trans_units(id),
  translated_by text, reviewed_by text, approved_by text,
  last_modified_by text, last_modified_at timestamptz
);
create index idx_units_chapter on trans_units (chapter_id, paragraph_index, unit_order);
create index idx_units_status on trans_units (status);

create table trans_revisions (
  id bigint generated always as identity primary key,
  display_id text unique not null, -- R000001
  unit_id bigint not null references trans_units(id),
  chinese_text text not null,      -- 冗餘快照
  english_before text, english_after text,
  revision_type text
    check (revision_type in ('terminology','tone','grammar','split','other')),
  note text,
  revised_by text, revised_at timestamptz default now(),
  -- T4.2（migration 010）：單一 embedding 欄位改為雙供應商並行，取代下面這行原設計：
  -- embedding vector(1536)
  embedding_voyage vector(1024),    -- Voyage AI voyage-3
  embedding_openai vector(1536)     -- OpenAI text-embedding-3-small
);
create index idx_revisions_unit on trans_revisions (unit_id);

-- find_similar_revisions_voyage(query_embedding vector(1024), match_limit int)
-- find_similar_revisions_openai(query_embedding vector(1536), match_limit int)
-- 兩支 RPC 各自對應欄位做 cosine 距離 ORDER BY <=> ... LIMIT，供 RAG 檢索使用
-- （PostgREST/supabase-py 無法直接表達 <=> 運算子，故用 RPC 包裝）

create table style_guide (
  id bigint generated always as identity primary key,
  display_id text unique not null, -- S000001
  category text check (category in
    ('honorifics','proper_nouns','sentence_splitting','tone','other')),
  rule_text text not null,
  example_before text, example_after text,
  active boolean default true,
  source_revision_ids bigint[],
  created_by text, created_at timestamptz default now()
);
```

> **display_id 產生**：以 Postgres sequence + `to_char` 格式化
> （如 `'T' || lpad(nextval('seq_terms_display')::text, 6, '0')`），
> 徹底告別 Sheets 時代掃全表找最大 ID 的競態問題。
