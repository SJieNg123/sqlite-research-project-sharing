# PLAN.md — Phase A0 探索與環境盤點（prefetch_warmer，Level 1）

> 本檔是 [README.md](README.md) 的 Phase A0 產出。三大塊：① 既有資產盤點、② 環境/API 實測結論、
> ③ 各 Phase 檔案清單與關鍵決策。所有「實測項」皆有實際指令輸出佐證（見各條註明）。

---

## ① 既有資產盤點（真實檔名 + 角色，皆已驗證存在/可執行）

| 路徑 | 角色 | 在本子專案怎麼用 |
|---|---|---|
| `classify_pages/classify_pages.c`（binary 已 build）| 精確頁面分類（走 freelist）| A1.1 抽出 O(1) 共享 `page_classify`；精確版保留為 **oracle**（驗活表、算 precision/recall、fallback）|
| `benchmark_harness/benchmark_harness`（+ `sqlite3.c`/`sqlite3.h`）| cold-start 量測引擎 + **SQLite amalgamation** | A3 量測；**VFS shim 直接 link 這份 `sqlite3.c`** |
| `residency_checker/residency_checker` | mincore 驗 page cache 殘留 | A2 驗證 warmer 真的把頁暖進 cache |
| `layout_rewriter/runs/evict` | `posix_fadvise(DONTNEED)` 無 root evict | A3 冷啟動前清 cache |
| `prefetch_access/src/prefetch_access` | 既有 madvise prefetch 原型 | 參考；新 warmer 取代之 |
| `prefetch_churn/measure_staleness.py`（本 session 新增）| `hot_key_coverage` 尺 | warmer 的 decay 健康檢查 |
| `prefetch_churn/runs_page_split/`（本 session 新增）| 搬頁 churn decay baseline | A3 decay 對照組 |

**`classify_pages` 實際輸出格式（實測）**：`page_number,page_type,file_offset`，吃一個 db 路徑參數。
範例 `1,leaf_table,0` / `2,interior_table,4096`。`page_type` ∈ {leaf_table, interior_table, interior_index,
leaf_index, …}。→ A1.1 的 O(1) 分類規則要對齊：interior_* → INTERNAL、leaf_* → LEAF。

---

## ② 環境 / API 實測結論

| 項目 | 實測結果 | 對設計的影響 |
|---|---|---|
| kernel | **6.17.0-19-generic** | 很新，io_uring/fadvise 全支援 |
| gcc | **15.2.0** | C 編譯無虞 |
| root? | **uid 1004，非 root** | ⛔ **不能 system-wide drop_caches** → 冷啟動只能靠 `posix_fadvise(DONTNEED)`/`MADV_PAGEOUT`（沿用 evict）；harness 量不到冷就**報錯中止（F5）** |
| SQLite | python 3.46.1；amalgamation 在 `benchmark_harness/sqlite3.{c,h}` | VFS shim 直接編這份，不另抓 |
| **liburing** | **未安裝**（pkg-config 找不到、無 header）；但 **io_uring syscall 在 kallsyms（kernel 支援）** | A2 暖法**主路徑改用 `posix_fadvise(WILLNEED)`/`readahead()`**；io_uring 列為**可選**（要嘛 `apt install liburing-dev`，要嘛自己包 raw `io_uring_setup/enter` syscall）。**不擋主線** |
| write-hint | `fcntl(F_SET_RW_HINT)` **OK，但只 per-inode（整檔）**；無 per-page/per-I/O write-life hint | 印證 **Level 1 不注入真 per-page kernel hint** → shadow tagging 純 metadata（真 per-page hint 是 Level 2 FEMU 的事）|

**關鍵結論**：

1. **無 root** 是硬約束 → 冷啟動量測沿用本 repo 既有的 fadvise/madvise 路線（已驗證 majflt 非零 = 真有 I/O）。
2. **無 liburing** → warmer 先用 `posix_fadvise`/`readahead`（簡單、夠用、與既有 evict 同路數）落地；io_uring 的 fan-out 平行讀當**加分項**，不是前置條件。
3. **無 per-page write hint** → 正好坐實 README §0 的判斷：Level 1 的 shadow tagging 是「旁邊記帳」、不改寫入行為，真 hint 留給 Level 2。

---

## ③ 各 Phase 檔案清單與關鍵決策

```
prefetch_warmer/
  README.md                 主控執行文檔（已寫）
  PLAN.md                   本檔（A0 產出）
  src/
    page_classify.{c,h}     A1.1 O(1) 共享分類 + unit test
    type_aware_vfs.{c,h}    A1.2 shim VFS（只 xWrite 多分類；委派 parent）
    hotset_dump.{c,h}       A1.3 活表 → <db>.hotset sidecar（含 file change counter@offset24）
    warmer.c                A2 獨立 warmer（fadvise/readahead 主、io_uring 選配）
    online_prefetch.{c,h}   A2.5 pointer-ahead + fan-out（線上語意預取，env 開關）
  runs/
    *.sh / *.csv            A3 ablation ladder 量測（L0..L5）+ precision/recall + held-out + decay 對照
```

**待決 / 風險**（A1 開工前確認）：

- **io_uring 要不要裝 liburing**：預設**先不裝**，warmer 用 fadvise 落地跑通 L0–L2；等做到 L4 fan-out 再決定裝 `liburing-dev` 或包 raw syscall。決策點記在這。
- **VFS link 方式**：用 `benchmark_harness/sqlite3.c` 靜態編進測試程式（單一 translation unit，避免版本不一致）。
- **drop-cache 無 root**：所有 A3 量測腳本沿用 `layout_rewriter/runs/evict`（fadvise DONTNEED）+ `--benchmark-cold-advice`；量不到冷就中止，不默默量（F5）。

**A0 驗證關卡狀態**：✅ PLAN.md 含三大塊；環境/API 每項皆有實測輸出佐證（kernel/gcc/uid/liburing/write-hint/classify 格式皆實跑）。下一步 → Phase A1。
