# Claude Code 執行提示詞：詞彙 Entity Type / Subject Field AI 分類

> 用途：貼給 Claude Code（本機 repo：`C:\Users\vince\code-projects\buddhist-vocab`），
> 一次性把 `terms.category`（自由文字）改造為結構化的 `entity_type` + `subject_field` 雙軸分類，
> 並加上 AI 自動建議、人員覆核修改的流程。
> 執行前請先用 `list_tables` / 讀一次 `terms` 表現況，確認欄位名稱與本提示詞一致再動工。

---

## 背景（分類設計原則）

兩個獨立分類軸，一個詞條可同時有兩者：

- **entity_type（詞條類型）**：這個詞「是什麼」。用途：決定翻譯處理方式（人名/地名通常音譯、不進 style guide 統計）。
  候選值：`人名` `地名` `寺院` `宗派` `書名典籍` `佛菩薩尊號` `概念術語` `其他`
  （`概念術語` 是預設／最大宗的一類，其餘是專有名詞細分）

- **subject_field（主題領域）**：這個詞屬於「哪個知識領域」。用途：翻譯 prompt 領域限定、術語一致性稽核。
  候選值：`教義` `戒律` `禪修` `因明` `儀軌法物` `稱謂教職` `歷史事項` `文學藝術` `其他`
  （參考《佛教大辭典》13大類簡化；`entity_type` 為專有名詞者，`subject_field` 可留空或標 `其他`）

> 註：若 Vincent 實際想要的是「佛教教育」這種弘法/教育類別而非「教義」，
> 執行前先跟他確認一次，再決定要不要把 `教義` 改成 `教義/教育` 或拆成兩個值。

---

## Part 1 — 資料庫遷移

在 repo 既有 migration 腳本模式下（`scripts/run_migration.py` 或對應目錄）新增一支遷移，**不要**用 MCP `apply_migration` 直接下（Vincent 偏好走版本控管的遷移檔案）：

```sql
alter table terms add column entity_type text
  check (entity_type in ('人名','地名','寺院','宗派','書名典籍','佛菩薩尊號','概念術語','其他'));

alter table terms add column subject_field text
  check (subject_field in ('教義','戒律','禪修','因明','儀軌法物','稱謂教職','歷史事項','文學藝術','其他'));

alter table terms add column classification_source text
  check (classification_source in ('ai','manual')) default null;

alter table terms add column classified_by text;
alter table terms add column classified_at timestamptz;

create index idx_terms_entity_type on terms (entity_type);
create index idx_terms_subject_field on terms (subject_field);
```

- 舊的 `category` 欄位**先保留、不刪**（避免既有查詢/UI 立即斷裂），遷移完成且 UI 切換穩定後再另開 PR 移除。
- 驗收：`\d terms` 能看到新欄位與 CHECK 約束；對現有列插入不合法值會被擋下。

---

## Part 2 — `ai.py` 新增分類函式

新增 `classify_term(term: dict) -> dict`，寫法沿用既有 `generate_term_data()` 的封裝與錯誤處理模式（同一個 Claude Haiku client、同樣的 retry/timeout 邏輯）。

輸入：`term` 至少含 `chinese`、`pinyin`、`context`、`notes`（沿用 terms 表既有欄位）。

Prompt 需求：
- 系統角色：佛學術語分類助手
- 明列上面兩軸的候選值清單（禁止自創新值，若都不符合就回 `其他`）
- 要求回傳結構化 JSON：`{"entity_type": "...", "subject_field": "...", "confidence": 0.0-1.0, "reasoning": "一句話理由"}`
- `confidence` 用於 UI 標示「AI 建議、但把握度低，建議人工確認」

呼叫端負責：寫入 `entity_type` / `subject_field`、`classification_source = 'ai'`、`classified_by = 'ai:claude-haiku-4-5'`、`classified_at = now()`。**不要**覆蓋已經是 `classification_source = 'manual'` 的詞條（除非呼叫端明確要求「強制重新分類」）。

---

## Part 3 — API 端點（`routes/` 對應 blueprint）

新增：
- `POST /api/terms/<id>/classify`　權限 member+　→ 呼叫 `classify_term()`，寫回上述欄位，回傳建議結果給前端（不強制人員採用）
- `POST /api/terms/classify_batch`　權限 leader+　→ 對一批 id（或 `entity_type IS NULL` 篩選）批次觸發，比照既有「批次翻譯由前端逐句驅動、CGI 不能背景任務」的限制，**同樣不能在單一 request 內迴圈呼叫 AI**——前端逐筆送出 + 進度條

修改既有：
- 詞條 `PATCH /api/terms/<id>`：若 payload 帶了 `entity_type` 或 `subject_field` 且與資料庫現值不同 → 該次更新自動設 `classification_source = 'manual'`、`classified_by = <當前使用者 email>`、`classified_at = now()`，並比照既有欄位變更寫入 `audit_log`（`field_changed = 'entity_type'` / `'subject_field'`）

---

## Part 4 — 前端 UI（詞條編輯 modal / 表單）

- 把現有 `category` 自由輸入框，換成兩個下拉選單（`entity_type`、`subject_field`），選項固定為上面候選值
- 新增「AI 建議分類」按鈕：呼叫 `POST /api/terms/<id>/classify`，回來後**自動帶入**下拉選單但保持可編輯；若 `confidence < 0.6`，在旁邊顯示提示文字（如「AI 把握度較低，請確認」）
- 小圖示區分來源：`classification_source = 'ai'` 顯示一個小 AI 標記，`manual` 不顯示（或顯示已確認勾勾）；人員一旦手動改值，圖示立即切換
- 詞彙列表頁：`entity_type` / `subject_field` 可作為篩選條件（下拉多選），方便之後做「戒律類詞彙」這種領域稽核

---

## Part 5 — 既有 828+ 筆詞彙批次回填

沿用專案既有模式（AI enrichment 用 `last_modified_at IS NULL` 當可續跑進度旗標）：

- 新增 `scripts/backfill_classification.py`
- 篩選條件：`entity_type IS NULL`（尚未分類）
- 逐筆呼叫 `classify_term()` 寫回 `entity_type` / `subject_field` / `classification_source='ai'`
- 可中斷續跑：已有值的列不會被重新處理
- 建議加一個 `--dry-run` 模式，先印出建議結果不寫入，供 Vincent 抽樣檢查再正式執行

---

## 驗收標準總覽

1. Migration 執行後，`terms` 表新增四欄位、CHECK 約束生效，插入非法值會報錯
2. 對單一詞條呼叫 `/api/terms/<id>/classify`，回傳的 `entity_type`/`subject_field` 落在候選值清單內
3. 人工在 UI 修改分類後存檔，`classification_source` 變成 `manual`，且 `audit_log` 出現對應紀錄
4. `backfill_classification.py --dry-run` 能對現有 828 筆詞彙跑出建議且不寫入；拿掉 `--dry-run` 後可中斷、可續跑、不重複處理已分類項目
5. 詞彙列表頁可用 `entity_type` / `subject_field` 篩選，篩選結果正確
