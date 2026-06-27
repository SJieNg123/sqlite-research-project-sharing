# Editorial Decision — REPORT.md 同儕審查綜整

> 由 academic-paper-reviewer skill（full mode）產生的模擬期刊審查編輯決定。
> 五位審稿人（EIC + 方法學 R1 + 領域 R2 + 跨域/實務 R3 + Devil's Advocate）獨立審查 [REPORT.md](REPORT.md) 後，由編輯綜整。
> 審查日期：2026-06-27 · Review Round 1 · 標準：PVLDB / FAST / SIGMOD / ATC / CIDR 級系統/DB venue。

---

## TL;DR — 研究主題與方向

**方向是對的、niche 是真的、但「論文怎麼宣稱」越過了證據能撐的範圍。** 五位審稿人一致認為：

- ✅ **題目站得住**：cold-start read path 確實被學界系統性忽略（連 SQLite 創始團隊的 Gaffney+22 都 `SELECT *` 預熱、把 cold-start 當 noise 排除）。
- ✅ **真正貢獻是 cost-accounting framing**（揭露「2f first-q −76~89% 但 e2e 慢一個量級」這個工程陷阱）——五人一致稱讚，是可發表的核心。
- ⚠️ **主線宣稱被一個會計選擇撐起**：「targeted prefetch 三 workload e2e 全贏」只在自選的 warm-process（不計 ~200µs cold open）下成立；改用 standalone，A/B 其實是輸的。**DA 與 R3 都評為 CRITICAL**。
- ⚠️ **真正穩健的大勝只有一格**（C × 2e_K10）；A 的 −7~9% 落在自承的 30–70% 機器漂移內。
- ⚠️ **通篇訴諸手機/IoT，零 mobile 證據**（全跑在一台桌機 NVMe）。

---

## Decision

### **Major Revision（大修，需重審）**

> 觸發 gating：Devil's Advocate C1 與 R3 W1 均評為 **CRITICAL**（warm-process 會計選擇撐起核心結論）。依審查紀律（DA CRITICAL → 不可 Accept），有 CRITICAL 未解前不可 Accept；但問題可由「重述框架 + 對稱呈現兩模型 + 收斂宣稱 + 補關鍵實驗」修復，故為 Major Revision 而非 Reject。

---

## Reviewer Summary

| Reviewer | 身分 | 建議 | 信心 | 加權分 |
|---|---|---|---|---|
| EIC | 儲存/DB 頂會主編 | Major | 4/5 | 66.0 |
| R1 | 系統量測 / reproducibility | Major | 5/5 | 66.7 |
| R2 | DB 儲存 / buffer management | Major | 5/5 | 70.0 |
| R3 | OS-kernel-mm / 行動嵌入式 | Major | 4/5 | 65.7 |
| Devil's Advocate | 核心論點挑戰 | （不可 Accept） | — | C1 = CRITICAL |

各審稿人維度評分（0–100）：

| Dimension | EIC | R1 | R2 | R3 |
|---|---:|---:|---:|---:|
| Originality | 66 | 80 | 62 | 74 |
| Methodological Rigor | 70 | 62 | 78 | 66 |
| Evidence Sufficiency | 64 | 64 | 70 | 60 |
| Argument Coherence | 66 | 70 | 72 | 70 |
| Writing Quality | 62 | 68 | 63 | 68 |
| **Weighted** | **66.0** | **66.7** | **70.0** | **65.7** |

---

## Consensus Analysis（共識分析）

### Points of Agreement

**[CONSENSUS-5]**（五人全同意）

1. **核心貢獻 = preprocessing cost-accounting framing**，確實補了 literature 空白；「2f first-q 最低卻 e2e 慢一個量級」是有教育價值、會被記住的發現。（EIC S3 / R1 S1 / R2 S1 / R3 S1 / DA Observations）
2. **「三 workload e2e 全贏」的 headline 被 warm-process 會計假設撐起**：扣不扣那 ~200µs cold open 決定 A 的勝負號（+27% ↔ −9%）。論文一邊「主張 warm-process」、一邊用 warm-process 前提消掉 open 成本，構成 circular framing。（EIC W1/W4 / R1 W3 / R2 隱含 / **R3 W1 CRITICAL** / **DA C1 CRITICAL**）
3. **真正穩健的大勝實質只有一格（C × 2e_K10, warm e2e −73%）**；A 是 ±7~9%、B 的 −29~34% 也只在 warm-process 成立。headline 寬度 > 證據寬度。（EIC W1 / R1 W1 / R2 隱含 / R3 / DA M1）
4. **外部效度過窄、且 motivation↔evidence 不對齊**：通篇訴諸 mobile/IoT/「>1T databases」，但全部證據來自單台 x86 桌機 NVMe、單 kernel、單一 102MB 單表 schema、ra=128 單值。（EIC W3 / R1 W4 / R2 次要 / R3 W2+W4 / DA m2）
5. **量測協定紀律與誠實報負面結果值得肯定**（drop-caches + mincore 雙驗 + majflt 驗證 + EPP 鎖頻 + hotset freeze；主動呈現 N=1 變慢、VACUUM 反效果）。（EIC S1 / R1 S3+S4 / R2 S4 / R3 S3 / DA Observations）

**[CONSENSUS-3+]**（3 人以上）

6. **小效應落在自承雜訊內**：30–70% 跨 session 漂移 + 明言「未做正式檢定」，A −7~9%（~40µs）與 batch noise（~5%≈26µs）同量級，違反論文 §3.7 自訂「落在雜訊內不宣稱排名」的標準。（R1 W1/W2 主責 / DA M2 / EIC 指派 R1 / R3 W1 呼應）
7. **novelty「first」過度宣稱**：InnoDB dump/load、Yi+26、Chen+21 都已觸及 prefetch 成本；真正可辯護的 novelty 較窄。（EIC W1 / R2 W2+W3 / DA M3）
8. **寫作**：中英混排密度過高、兩個部署模型定義重複多處、標題過於通用未傳達 selling point。（EIC / R1 / R2 / R3 全提）

**[CONSENSUS-2]**

9. **「page-type-aware」混淆了 layout 與 selection 兩個槓桿**：最佳結果（C 2e_K10）其實由 access-frequency 選熱 leaf 驅動，非 page-type；需 ablation 分離。（R2 W4 主責 / R3 呼應）
10. **「interior=0.35%」是 B+tree 教科書常識，非發現**；應降溫，把機制工作提為 headline。（R2 W3 / DA m1）

### Points of Disagreement

**Disagreement 1：warm-process 會計問題的嚴重度**
- **R3 + DA**：CRITICAL —— 「用結論挑有利會計口徑」，gating。
- **EIC + R1 + R2**：Major —— 合法 scoping，但須對稱呈現、補部署普遍性論證。
- **類型**：Severity disagreement。
- **編輯裁決**：依保守原則 + IRON RULE，**採 CRITICAL-gating**（不可 Accept），但認定可由重述修復 → 整體 Major Revision。理由：R1 提出的技術精修使這點無可迴避（見 Disagreement 2），且兩位資深審稿人獨立評為 CRITICAL。

**Disagreement 2：warm-process 模型內，−7~9% 的勝負來源**
- **EIC / R3 / DA**：把勝負歸因於「省掉那次 cold open」。
- **R1（技術精修）**：**歸因錯置**。warm-process 下 baseline 與 prefetch 都不含 open，故 warm 模型內 prefetch vs baseline 的勝負 = `fq 改善 − deliver`，與 open 無關；open 只決定 warm vs standalone 兩模型之差。
- **類型**：Direction / 機制歸因 disagreement。
- **編輯裁決**：**R1 正確**（信心 5/5、屬其專長）。論文 §5.2/§5.5.3/§6.1 多處「差別就是那一次 cold open」在 warm 模型內是錯的。作者須：(a) 明確區分「warm vs std 之差 = open」與「warm 內勝負 = fq−deliver」；(b) 兩模型對稱呈現。此裁決同時強化 Disagreement 1 的 gating 性質。

**Disagreement 3：論文主軸該擺哪**
- **EIC**：把 C3 cost-accounting 提為唯一主軸。
- **DA**：2f 的「first-q 最低但 e2e 輸」在兩模型下方向一致（更穩健），比 targeted 的勝利更該當主軸。
- **類型**：Perspective difference。
- **編輯裁決**：兩者相容 —— 主軸定為 **cost-accounting framing**，而 **2f 反差**作為該 framing 下最穩健的證據範例（不依賴會計口徑），targeted 的勝利則誠實收斂到 robust 的格子。

---

## Decision Rationale

本文題目與方向獲五位審稿人一致肯定：cold-start read path 是被學界系統性忽略的真實 niche（EIC S1 用 Gaffney+22 的 `SELECT *` 預熱釘死此點），而 preprocessing cost-accounting framing 是真正補空白、且有跨子社群方法論警示價值的貢獻（CONSENSUS-5 #1）。量測紀律亦達 strong 水準（CONSENSUS-5 #5）。因此這不是一篇方向有問題的論文，而是一篇**宣稱超出證據**的論文。

不能 Accept 的關鍵在於 CONSENSUS-5 #2 / Disagreement 1：核心 headline「targeted prefetch 三 workload e2e 全贏」由作者自選的 warm-process 會計口徑撐起，改用其自己列為合法的 standalone 模型，A/B 即翻為輸（EIC W1、R3 W1-CRITICAL、DA C1-CRITICAL）。R1 進一步證明論文對此勝負的歸因本身有誤（Disagreement 2）。疊加小效應落在自承雜訊內（CONSENSUS #6）、真正穩健大勝僅一格（#3）、mobile 宣稱零 mobile 證據（#4）、novelty「first」過廣（#7），這些都是結構性、需新分析與重述、而非潤飾的問題。

選 Major 而非 Reject：所有問題都可由「框架重述 + 兩模型對稱 + 宣稱收斂 + 補一兩個關鍵實驗」修復，核心貢獻不需推翻。選 Major 而非 Minor：涉及 CRITICAL gating + 需新實驗（ablation、ra sweep、cap<working-set、ARM sanity）。

---

## Required Revisions（必改）

| # | 修訂項 | 來源 | 嚴重度 | 章節 | 估時 |
|---|---|---|---|---|---|
| **R1** | **對稱呈現兩個部署模型**：Abstract/§8 headline 不得只用 warm-process；兩模型並陳，或以 standalone 為主口徑。明確論證 warm-process 普遍性（引用 app lifecycle 證據），並標明哪些 motivation 場景屬 warm、哪些屬 standalone（休眠喚醒/被 LMK 殺後重啟其實接近 standalone） | DA C1 / R3 W1 / EIC W1+W4 | **Critical** | Abstract, §3.4, §5.5, §8 | 5–8 天 |
| **R2** | **修正 warm 模型內歸因**：區分「warm vs std 之差 = open」與「warm 內 prefetch vs baseline 勝負 = fq − deliver」；改寫 §5.2/§5.5.3/§6.1 | R1 W3 | **Critical** | §5.2, §5.5.3, §6.1 | 1–2 天 |
| **R3** | **收斂貢獻寬度 + 補不確定性**：對每個被宣稱的勝負報配對差離散度（IQR / bootstrap CI / paired Wilcoxon）；凡 \|效應\|≲ batch noise（A −7~9%）改述「打平/方向性傾向」，與 §3.7 自訂標準自洽 | R1 W1+W2 / DA M2 / EIC | **Major** | §3.7, §5.2, §5.5.2, §6.3 | 5–7 天 |
| **R4** | **對齊 mobile 宣稱與證據**：二擇一 ——(a) 補一台 ARM/UFS SBC 跑 A/C × {baseline, 2e_K10} 關鍵 cell；或 (b) 全面把 claim scope 收到「commodity desktop NVMe」，標題/摘要據此定錨 | EIC W3 / R3 W2 | **Major** | Abstract, §1, §3.6, §6.4 | (a) 1–2 週 / (b) 2 天 |
| **R5** | **收斂 novelty 宣稱**：把「first to bring preprocessing into e2e」改為帶 scope 的窄宣稱；明確相對 InnoDB dump/load、Yi+26、clustering/`CLUSTER`/IOT 傳統定位 layout rewriter | EIC W1 / R2 W2+W3 / DA M3 | **Major** | Abstract, §1 C3, §2.3.2, §4.1 | 3–4 天 |

---

## Suggested Revisions（建議改）

| # | 修訂項 | 來源 | 優先 | 章節 |
|---|---|---|---|---|
| S1 | **加 ablation 分離三槓桿**：(i) layout clustering、(ii) 原 layout 上的 page-type selection、(iii) access-pattern leaf selection；說明各 workload 由哪個主導（最佳 C 結果其實是 leaf-frequency 驅動） | R2 W4 | P2 | §5 新節 |
| S2 | **ra 不再單值**：補 ra∈{64,128,512} spot-check（sysfs 寫權限或同類 setuid wrapper，不必 root）；否則明確把所有 async 結論 scope 到 ra=128 | R1 W4 / R3 W4 | P2 | §3.5, §6.4 |
| S3 | **修 RAM-pressure 軸**：cap 設到顯著低於 working set（4M/8M/12M ladder），用 mincore 量 first-query 前 prefetch 過的 interior 殘留率（cgroup v2 `memory.max` + `memory.stat`） | R3 W3 | P2 | §6.2.2 |
| S4 | **補競爭 baseline 對拼**：在「同樣計入 preprocessing」下，把 Yi+26 hotspot 選擇或認真調校的 dump/load 移植對拼，證明 2f 非稻草人 | EIC W2 | P2 | §5 |
| S5 | **補中間 delivery 點**：測 `readahead(2)` 或「madvise + 固定 sleep」中間點，量 fq_async 逼近 fq_pread 的程度（現 delivery loss 可能被 harness 緊湊時序高估） | R3 W5 | P3 | §3.5 |
| S6 | **補/修引用**：補上 dangling 的 [Yang+20 Leaper]（其 uniform 零加速 = 本文 B workload ceiling 的最近類比）、CacheLib（cache admission）、LeanStore；§2.3.1 的「候選 reading」改為正式引用或刪除 | R2 W1 | P2 | §2.3, §9.2 |
| S7 | **降溫「0.35%」**：從「關鍵 observation」降為「已知 B+tree 結構事實」，一句 fanout 算術即可化解 | R2 W3 / DA m1 | P3 | Abstract, §1, §2.1 |
| S8 | **澄清 layout rewriter（1c）淨價值**：§6.1 自承 1c 把 A/B baseline 推高，明確給 1c 的 net-win 條件，或誠實降級為探索性負面結果 | EIC W5 / DA m4 | P3 | §4.1, §6.1 |

---

## Revision Roadmap

### Priority 1 — 結構性（必改，~2 週）
- [x] R1 兩模型對稱 + warm-process 普遍性論證 + motivation 場景歸類
- [x] R2 修正 warm 模型內歸因
- [x] R3 補不確定性 + 收斂小效應宣稱 — **10-seed workload-sensitivity sweep**(同 DB、10 條不同抽樣的 A/B/C × full matrix)，每格報 bootstrap 95% CI + 符號一致性 + verdict。結論：access-pattern targeted prefetch 三 workload warm e2e 皆 robust(A 2e_K10 −36%[−50,−23]、B 2d −25%、C 2e_K10 −70%[−72,−69]、CI 皆不跨 0)；structural layers_5 在 A/B 落雜訊內(A tie、B directional)。新 §3.7 方法 + §6.2.4 結果 + overall_results.md 全表；`tools/{gen_workload,stats_uncertainty}.py` + `results/seeds/`。
- [x] R5 收斂 novelty「first」+ 定位 layout rewriter 於 clustering 傳統

### Priority 2 — 內容補充（~1–2 週）
- [ ] R4 ARM sanity check 或全面 scope 到 desktop
- [ ] S1 三槓桿 ablation
- [ ] S2 ra sweep
- [ ] S3 真 RAM pressure（cap < working set）
- [ ] S4 競爭 baseline 對拼
- [ ] S6 補/修引用

### Priority 3 — 文字與格式（~3 天）
- [ ] S5 中間 delivery 點
- [ ] S7 降溫 0.35%
- [ ] S8 澄清 1c 淨價值
- [ ] 統一 churn 規模數字不一致（摘要 50k vs §6.2.1 11×5k=55k vs §3.6 50k×10）
- [ ] 統一中英術語密度
- [ ] 標題改為點出 cost-accounting
- [ ] 圖 14 內嵌並簡化（標「翻盤是否落在 noise 內」）

### 總估時
- **Major Revision ≈ 5–7 週**

---

## Severity → Priority 對照

| Severity | Priority | Revision Type |
|---|---|---|
| Critical | P1 | Required（R1, R2） |
| Major | P1/P2 | Required（R3, R4, R5） |
| Minor | P2/P3 | Suggested（S1–S8） |

---

## Closing

本文方向有價值、核心 framing 與量測紀律值得肯定；但需實質重構「宣稱 vs 證據」的對齊，並補關鍵實驗。請逐條回應每位審稿人意見後重新投稿，修訂稿將再經一輪審查。

---

*本檔為 Phase 2 編輯綜整。Phase 1 的五份完整審稿報告未併入本檔（如需，可另行輸出）。所有綜整點均可回溯至 Phase 1 報告，無捏造。*
