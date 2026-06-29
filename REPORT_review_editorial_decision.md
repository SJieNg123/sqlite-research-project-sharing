# Editorial Decision — REPORT.md 同儕審查綜整（Round 2）

> 由 academic-paper-reviewer skill（full mode）產生的模擬期刊審查編輯決定。
> 五位審稿人（EIC + 方法學 R1 + 領域 R2 + 跨域/實務 R3 + Devil's Advocate）**獨立**審查修訂後的 [REPORT.md](REPORT.md)（blind to Round 1）後，由編輯綜整。
> 審查日期：2026-06-29 · **Review Round 2** · 標準：PVLDB / FAST / SIGMOD / ATC / CIDR 級系統/DB venue。
> 註：Round 1 的決定與 roadmap 已存於 git history（本檔覆寫前的版本），其完成狀態已 carry forward 至下方「Revision Roadmap」。

---

## TL;DR — 這一輪的結論

**Round-1 的 gating CRITICAL（warm-process 會計撐起核心結論）已被解除。** Devil's Advocate 這次專門壓力測試該框架後**未開任何 CRITICAL**——「框架沒有造假，最強的格子（C × 2e_K10）經 10-seed robust 驗證為真」。

- ✅ **三槓桿 ablation（§5.4.1）五人一致盛讚**：`leaf_rand` −2% vs `leaf_freq` −40%（同型別同張數）是教科書級 causal isolation，且主動修正「page-type-aware」命名。
- ✅ **可重現性是真強項**：R1 獨立把所有 headline 數字、cross-seed CI、ablation、1gb、RAM、deliver_sweep 對回 CSV，**零 mismatch**。
- ✅ **selection–delivery 拆解 + intermediate-delivery sweep（§3.5/§3.5.1）**被多位評為比 cost-accounting headline 本身更紮實。
- ⚠️ **仍有一個會威脅結論的缺口需新實驗**：唯一被細測的 dump 對照 `2f_slru` 是 blind full-dump（strawman），缺 frequency-ranked **partial** dump 對照——「targeted 贏 dump」可能其實只是「ranked-partial 贏 unranked-full」。
- ⚠️ **框架用詞仍偏滿**：「首個 end-to-end cost-accounting」、Abstract「三 workload 皆贏」掛未校正的單格 A/B 數字、Index Terms 仍以 page-type 領銜、mobile motivation 仍蓋過 desktop-only 證據。

---

## Decision

### **Major Revision（大修）— focused / borderline-Minor**

> 觸發理由：**沒有任何 CRITICAL 存活**（DA 解除了 Round-1 gating；R2 的「首個」CRITICAL 可由 re-wording 化解，屬 Minor 級修法）。但有**一個會威脅結論的缺口需要新實驗**（competitive partial-dump baseline，R2 W2 + DA），再加上仍 open 的 ra-sweep，整體超出 Minor。其餘（收斂宣稱、Abstract 重平衡、framing 收斂）皆 text-level。核心貢獻 sound 且五人一致肯定——**這是通往 Accept 的短路徑，不是變相 Reject**。

---

## Reviewer Summary

| Reviewer | 身分 | 建議 | 信心 |
|---|---|---|---|
| EIC | 儲存/DB 頂會主編 | **Minor Revision** | 4/5 |
| R1 | 系統量測 / reproducibility | **Minor Revision** | 5/5 |
| R2 | DB 儲存 / buffer management | **Major Revision** | 4/5 |
| R3 | OS-kernel-mm / 行動嵌入式 | **Minor Revision** | 4/5 |
| Devil's Advocate | 核心論點挑戰 | **無 CRITICAL**（"oversold but core holds"） | — |

各審稿人維度評分（0–100）：

| Dimension | EIC | R1 | R2 | R3 | 平均 |
|---|---:|---:|---:|---:|---:|
| Originality | 72 | 78 | 62 | 78 | **72.5** |
| Methodological Rigor | 78 | 84 | 84 | 82 | **82.0** |
| Evidence Sufficiency | 70 | 82 | 72 | 75 | **74.8** |
| Argument Coherence | 80 | 80 | 80 | 84 | **81.0** |
| Writing Quality | 62 | 70 | 70 | 70 | **68.0** |

---

## Consensus Analysis（共識分析）

### Points of Agreement（強項，五人一致）

1. **§5.4.1 三槓桿 ablation 是模範**：五人都點名其 causal isolation（`leaf_rand` 同型別同張數對照 −2% vs `leaf_freq` −40%）並肯定主動修正命名。（EIC S3 / R1 S1 / R2 S2 / R3 / DA Obs 1）
2. **可重現性是真強項**：R1 逐格重算 headline / cross-seed CI / ablation / 1gb / RAM / deliver_sweep，**零 mismatch**。（R1 S1 / DA Obs 4）
3. **selection–delivery 拆解 + intermediate-delivery sweep（§3.5/§3.5.1）**：可能比 cost-accounting headline 本身更站得住。（R1 S2 / R2 S3 / R3 S1 / DA Obs 3）
4. **誠實面對負面結果與自我修正**：1c layout 標為探索性負面結果、§6.2.4 cross-seed 推翻單批 headline。（EIC S4/S5 / R2 S4 / DA Obs 2/5）

### 多位審稿人共同點名（必須處理）

| 主題 | 嚴重度 | 來源 | 對應 roadmap |
|---|---|---|---|
| **「首個 end-to-end cost-accounting」over-claim** — 收斂為「OS-syscall 粒度的 open/deliver 拆解 + pread-oracle 隔離 delivery loss、於 SQLite cold-start」 | R2 **CRITICAL** W1 / EIC MAJOR / DA MINOR | 用詞修正 | （R5 復現） |
| **2f_slru 是 strawman，缺 competitive baseline** — 需 frequency-ranked **partial** dump（`2f_topN`）；勝負是「targeted vs dump」還是只是「ranked-partial vs unranked-full」？ | R2 **MAJOR** W2 / DA alt-path / R1 implied | **新實驗** | **= open S4** |
| **mobile motivation 仍蓋過 desktop-only 證據**（即便已做 R4 scoping） — 把 mobile 退為「motivating context」，敘事改以 commodity-NVMe / serverless 領銜 | R3 MAJOR / DA MAJOR / EIC MAJOR | reframing | （延伸 R4） |
| **Abstract over-claim「三 workload 皆贏」+ 掛未校正單格 A/B 數字** — 改用 cross-seed CI、明標 A/B `layers_5` 為 tie/directional | DA MAJOR / R1 implied / EIC | abstract 重寫 | — |
| **page-type branding（Index Terms/§1）與 ablation 結論衝突** — access-frequency 提到同等地位 | R2 MAJOR W3 / DA MINOR | reframing | （延伸 S1） |
| **`ra=128` 單值** — 掃 {0,64,512} 關鍵 cell，否則把「readahead 養熱」gap 解釋降為未驗證 conjecture | R3 MAJOR | 小實驗 / scope | **= open S2** |
| **寫作**：中英 code-switch 過密、Abstract 單段、typo（「走full條 path」） | EIC/R1/R2/R3 全 MINOR | 潤飾 | — |

### Points of Disagreement（整體嚴重度）

- **R2**：Major（novelty + competitive baseline 是 DB-storage 領域不可放行的核心缺口）。
- **EIC / R1 / R3**：Minor（皆可由收斂宣稱 + 一兩個實驗修補）。
- **DA**：無 CRITICAL，「core holds but oversold」。

**編輯裁決**：R2 的 W1「首個」CRITICAL **可由 re-wording 化解**（→ Minor 級），故不單獨構成 Major。但 R2 W2（competitive baseline）與 R3 ra-sweep 都需新跑，且 competitive-baseline 缺口**會威脅結論**（最懂這條軸的 R2 以 4/5 信心評為 Major）。據此整體定為 **focused Major**。核心貢獻 sound 且五人一致肯定，通往 Accept 的路徑清楚而短。

---

## Decision Rationale

本輪相對 Round 1 有實質進步：**Round-1 的雙 CRITICAL（warm-process 會計撐起結論）已解除**——DA 專門針對此點壓力測試，結論是「框架沒有造假；即使只看 baseline 對稱、cross-seed robust 的最保守證據，C × 2e_K10 的勝利仍為真（−70% [−72,−69]、10/10 seed）」。量測紀律、可重現性、ablation 的自我修正皆達 strong 水準（維度均分 Rigor 82 / Coherence 81）。

不能直接接收的關鍵：**唯一被細測的 dump 對照（2f_slru）是未經調校的 blind full-dump**。R2（W2）與 DA（替代路徑）獨立指出：2f 之所以 e2e 輸，是因為它 deliver 了整份 working set（~4.4k page）而非像 2e_K10 只 deliver ~14–28 page——這是「dump 多少」的差，非「dump 機制 vs targeted 機制」的本質差；而 2e_K10 本身就是一種 frequency-ranked partial dump。若一個 `dump_pct` 調得當的 partial dump 與 2e_K10 打平，mechanism novelty 即蒸發。這需要**新實驗**（`2f_topN`），故超出 Minor。

選 Major 而非 Reject：核心貢獻不需推翻，五人一致肯定；缺口可由「一個 competitive baseline 實驗 + 收斂宣稱 + Abstract/ framing 紀律」修補。選 Major 而非 Minor：涉及一個會威脅結論的新實驗（RR1 = S4）+ 仍 open 的 ra-sweep（SR1 = S2）。

---

## Required Revisions（必改）

| # | 修訂項 | 來源 | 嚴重度 | 需要 |
|---|---|---|---|---|
| **RR1** | **補 competitive frequency-ranked partial-dump baseline**（`2f_topN`，N∈{14,28,100,500}）置於同一 e2e accounting。證明 `2e_K10` 是否仍勝過 tuned partial dump；若打平，把貢獻重定位為「cost-accounting 方法學 + partial-dump frequency sweet-spot 量化」 | R2 W2 / DA | **Major** | 新實驗 **(= S4)** |
| **RR2** | **收斂「首個」novelty 宣稱**（Abstract/§1-C3/§8）為 syscall 粒度 + pread-oracle framing；把 §2.3.2「差異在粒度、非是否意識到成本」提升為 contribution 主述句 | R2 W1(CRIT) / EIC / DA | Major→ 用詞 | text |
| **RR3** | **Abstract 重平衡**：單格 A/B 數字改為 cross-seed CI；明標 structural `layers_5` 在 A/B 為 tie/directional；cost-accounting finding 前置為 headline；拆解超長單段 | DA / R1 / EIC | Major | text |
| **RR4** | **framing 收斂到 commodity-NVMe / serverless**：Abstract 首句與 §1 明確把 mobile/IoT 定位為「motivating context、非 evaluated platform」；§2.3.3 改框為與 read-path 正交的 write-path lineage | R3 / DA / EIC | Major | text |
| **RR5** | **access-frequency 提到與 page-type 同等地位**（Index Terms / §1），與 §5.4.1 結論一致 | R2 W3 / DA | Major | text |

---

## Suggested Revisions（建議改）

| # | 修訂項 | 來源 | 優先 |
|---|---|---|---|
| SR1 | `ra` 掃 {0,64,512} 於 A `layers_5` / C `2e_K10`，否則把「readahead 養熱」gap 解釋降為 labeled conjecture | R3 **(= open S2)** | P2 |
| SR2 | 補強 §3.7 統計：報 bootstrap resample 次數、CI type（BCa vs percentile 及其 n=10 侷限）、加 sign-test/Wilcoxon sanity check | R1 | P2 |
| SR3 | 報 `open_us` 變異（p95/stdev）；加一列「baseline+open」的 standalone，呈現 open 是 common-mode 還是 prefetch-only | R1 / DA | P2 |
| SR4 | 把 workload C 的 RAM-robustness 標為**演繹**（WS < 量測下限），或構造放大-WS 的 C 變體取得真 sub-WS datapoint | R3 | P2 |
| SR5 | §2.1：「所有 interior 必須駐留」改為「單筆 query 需 root→leaf path 的 interior（≈ tree height）；累積則需 working-set 內的 interior 子集」 | R2 W5 | P3 |
| SR6 | §3.4：明述 hotset-generation 是 offline/amortized（引 §6.2.1 churn 不 decay），避免被質疑藏了 access-pattern 策略最貴一步 | R2 W6 / DA | P3 |
| SR7 | 寫作潤飾：降中英混雜密度、修 `full`/`shared` find-replace typo、加「如何讀 e2e 表」3 行 reader's guide | 全體 | P3 |
| SR8 | 修 figure-6 caption（unlimited 分母 = 同 session、非 results/main）；註明 deliver_sweep/§3.5.1 baseline 屬不同批；suppress 近零分母的 recovery% | R1 / R3 | P3 |

---

## Revision Roadmap

### Round 2 — 本輪必改/建議
- [ ] RR1 競爭性 partial-dump baseline（`2f_topN`）— **= open S4**，需新實驗
- [ ] RR2 收斂「首個」novelty 用詞
- [ ] RR3 Abstract 重平衡（cross-seed CI + 標 layers_5 不 robust + 拆段）
- [ ] RR4 framing 收斂到 commodity-NVMe / serverless、mobile 退為 motivation
- [ ] RR5 Index Terms / §1 提升 access-frequency 至同等
- [ ] SR1 ra-sweep — **= open S2**
- [ ] SR2 §3.7 bootstrap CI 方法補強
- [ ] SR3 open_us 變異 + standalone「baseline+open」列
- [ ] SR4 C 的 RAM-robustness 標為演繹 / 補放大-WS datapoint
- [ ] SR5 §2.1 interior 駐留表述修正
- [ ] SR6 §3.4 hotset-generation amortized 界定
- [ ] SR7 寫作潤飾 + reader's guide
- [ ] SR8 figure-6 caption + 跨批 baseline 註記 + 近零分母 suppress

### Round 1 — 完成狀態（carry forward；詳版見 git history）
- [x] **P1 結構性**：R1 兩模型對稱、R2 warm 模型內歸因、R3 不確定性（10-seed sweep）、R5 收斂 novelty + layout rewriter 定位
- [x] **P2 內容**：R4（採出路 b：scope 到 commodity desktop NVMe）、S1（三槓桿 ablation，§5.4.1 + 圖 17）、S3（sub-WS RAM-pressure，§6.2.2 + 圖 16）
- [ ] **P2 仍 open**：S2（ra sweep）→ 本輪 SR1 重申；S4（競爭 baseline）→ 本輪 RR1 升為必改
- [x] **P3 文字格式**：S5（intermediate-delivery sweep）、S7（0.35% 降溫）、S8（1c 淨價值澄清）、churn 規模統一、術語密度、標題 cost-accounting 定錨、圖 14 ‡ 標記
- [x] **額外**：DB-size scaling（§6.2.5 + 圖 15）、資料可比性方法學（2f_slru 錨點）

### 觀察：本輪與既有 roadmap 的對齊
本獨立 Round-2 審查**收斂於兩個仍 open 的項目**：**RR1 = S4**（競爭 baseline）、**SR1 = S2**（ra-sweep）。超出 Round 1 的新要求（RR2–RR5）全是 **text/framing**：收斂「首個」、Abstract 改用 cross-seed CI、framing 收斂到 commodity-NVMe、提升 access-frequency。**Round-1 的 CRITICAL（warm-process 會計）已清除。**

### 總估時
- **Focused Major Revision ≈ 1.5–2.5 週**（RR1 一個實驗 + RR2–RR5 與 SR 多為改寫）

---

## Severity → Priority 對照

| Severity | Priority | Revision Type |
|---|---|---|
| Major（需實驗/威脅結論） | P1 | Required（RR1） |
| Major（用詞/framing） | P1 | Required（RR2–RR5） |
| Minor | P2/P3 | Suggested（SR1–SR8） |

---

## Closing

修訂稿相對 Round 1 進步明顯：**Round-1 gating CRITICAL 已解除**，量測紀律、可重現性、ablation 的自我修正獲五人一致肯定，最穩健的核心結果（C × 2e_K10，−70% [−72,−69]、10/10 seed）經 adversarial stress-testing 仍成立。通往 Accept 的路徑短：**一個 competitive-baseline 實驗（RR1/S4）+ ra-sweep（SR1/S2）+ 收斂宣稱與 Abstract/framing 紀律**。請逐條回應每位審稿人意見後重新投稿，修訂稿將再經一輪審查。

---

*本檔為 Phase 2 編輯綜整（Round 2）。Phase 1 五份完整審稿報告未併入本檔；所有綜整點均可回溯至 Phase 1 報告，無捏造。*
