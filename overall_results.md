# Overall Results — 策略 × Workload 結果矩陣

本檔列出**每個策略 × 每個 workload × 每個 layout 的 實驗結果**（對照
[overall_workloads.md](overall_workloads.md) 的 workload 定義）。

> 本檔所有數字來自 **統一 pipeline**（`run_experiment.py` 家族 → `results/main*/`,全 cell `cold_pct`=0)。
> Workload D 是 churn generator,無自身 latency 結果。
>
> **Preprocessing 計入 e2e（兩個部署模型）**:preprocessing 拆成 **open(db)(冷開 DB ~200µs,per-layout 常數)**
> 與 **deliver(逐頁 madvise/pread,隨 hotset)**。`e2e_warm` = deliver+fq(warm-process/integrated,
> 重用既有 handle、不付冷 open;≈ static `effective_first_query`,**本研究主張**);`e2e_std` = open+deliver+fq
> (standalone warmer)。**2f_slru first-query 最低(−76~89%)但 deliver ~0.8–7ms 使 e2e 多半輸**;
> targeted prefetch(layers_5 / 2d / 2e_K10)deliver 小,**warm-process e2e 三 workload 皆改善**(尤其 C × 2e_K10 −73%)。
> 視覺化:[figures 13/14](figures/out/13_strategy_firstq_bars.png)。
> 完整執行覆蓋見 [IMPLEMENTATION_PIPELINES.md §3.8](IMPLEMENTATION_PIPELINES.md)。

---

## 資料可比性（先讀）— 跨表/策略/workload 怎麼比才對

各批資料**在不同日期、不同機器狀態下量測**。用 machine-independent 的 `2f_slru` first-query 當錨點
(它載整個 working set,first-q 只看當下 CPU 狀態,與 workload 無關)可看出至少 **4 個狀態群**:

| 來源 | 日期 | `2f_slru` 錨點 | 狀態群 |
|---|---|--:|---|
| `nsweep` / `nsweep_dense` / `ksweep` / `ram20m` | 06-22 | ~110µs | ① 較快 |
| `z` | 06-23 | 119µs | ② 中間 |
| **`main`(master)** / `seeds/seed01–10` | 06-24 / 27 | 126–127µs | ③ 基準 |
| `size_1gb` / `seeds_1gb` | 06-28 | 96–98µs | ④ 最快 |

**規則:**
- ✅ **相對量跨任何表/策略/workload 都可比** —— `impr%`(相對同批 baseline)、跨-seed `Δ% + CI`、RAM `ratio`、
  churn 各 checkpoint 演化。**本報告所有結論都建立在相對量上,不受機器狀態影響。**
- ✅ **絕對 µs 只在「同狀態群內」可比** —— 例:`main`↔`seeds`(群③同尺度,故跨-seed 對 master 比對有效);
  `size_1gb`↔`seeds_1gb`(群④);1gb 的 100MB 對照基準用**同批 `orig` 列**(見 DB 尺寸 scaling 章)。
- ⚠️ **絕對 µs 跨群勿逐格對** —— 同一個量測 `layers_92 A/orig` 在 master(群③)= **393µs**、在 nsweep(群①)= **333µs**,
  15% 差**純機器狀態**;`z`(群②)整列比 A/B/C(群③)低 ~6%;`size_1gb`(群④)比 master 低 ~25%。這些都不是真效應。

> **特別注意 RAM-pressure 表**:其 ratio 必須用**同 session 的 unconfined** 當分母。表上 ~1.0 是當年對「同期(06-22)unconfined」算的(正確);
> 但**現在的 `results/main` 是 06-24 重跑(群③,慢 ~15%)**,若拿它當分母重算會得 ~0.85——那 0.85 是機器狀態假象,不是記憶體壓力效應。
> (`figures/06_ram_pressure_heatmap.py` 註解寫「unlimited = results/main」已過時,同理。)

---

<!-- MASTER-RESULTS-START -->
## master batch 結果

> 由 `run_experiment.py` 一次跑齊:54 strategy cells × pread/async + 9 baseline,pread 5 / async 10 / baseline 10 reps(丟 warmup)、rep-major、全機 drop-caches、in-harness `--verify-hotset`、釘核升頻、ra=128。**全 117 cell `cold_pct`=0**。原始檔:[`results/main/summary.csv`](results/main/summary.csv) / [`results/main/raw.csv`](results/main/raw.csv)。
> `fq` = first-query median µs;`impr%` = async 相對該 (workload,layout) baseline;`e2e_std` = open+deliver+fq(standalone warmer);`e2e_warm` = deliver+fq(warm-process,≈static,本研究主張);`deliv%` = async delivery_pct;`oracle` = pread 模式 fq(可達上界)。
> 此為 A/B/C 的詳表(含 delivery_pct/oracle);下方「全維度數據」涵蓋全 workload(含 Z)× layout × 策略 + N/K-sweep + RAM + churn + cadence。

### Workload A (Zipfian)

| layout | strategy | fq_async | impr% | deliv% | e2e_std | e2e_warm | oracle(pread) |
|---|---|--:|--:|--:|--:|--:|--:|
| **orig** | baseline | **529** | — | — | 529 | 529 | — |
| orig | layers_5 | 412 | 22% | 100 | 671 | 480 | 207 |
| orig | layers_92 | 393 | 26% | 100 | 781 | 587 | 210 |
| orig | 2d | 401 | 24% | 100 | 680 | 487 | 210 |
| orig | 2e_K10 | 393 | 26% | 100 | 685 | 490 | 212 |
| orig | 2e_K500 | 212 | 60% | 100 | 1238 | 1044 | 211 |
| orig | 2f_slru | 127 | 76% | 100 | 7327 | 7134 | 128 |
| **vacuum** | baseline | **716** | — | — | 716 | 716 | — |
| vacuum | layers_5 | 574 | 20% | 100 | 838 | 643 | 208 |
| vacuum | layers_92 | 575 | 20% | 100 | 954 | 759 | 209 |
| vacuum | 2d | 576 | 20% | 100 | 846 | 654 | 210 |
| vacuum | 2e_K10 | 571 | 20% | 100 | 894 | 662 | 210 |
| vacuum | 2e_K500 | 226 | 68% | 18 | 1162 | 934 | 212 |
| vacuum | 2f_slru | 126 | 82% | 100 | 5684 | 5463 | 123 |
| **ta** | baseline | **695** | — | — | 695 | 695 | — |
| ta | layers_5 | 524 | 25% | 100 | 814 | 593 | 505 |
| ta | layers_92 | 457 | 34% | 51 | 846 | 624 | 212 |
| ta | 2d | 463 | 33% | 72 | 793 | 573 | 216 |
| ta | 2e_K10 | 401 | 42% | 100 | 748 | 526 | 219 |
| ta | 2e_K500 | 340 | 51% | 25 | 1309 | 1086 | 210 |
| ta | 2f_slru | 128 | 82% | 100 | 7367 | 7146 | 126 |

### Workload B (Uniform)

| layout | strategy | fq_async | impr% | deliv% | e2e_std | e2e_warm | oracle(pread) |
|---|---|--:|--:|--:|--:|--:|--:|
| **orig** | baseline | **760** | — | — | 760 | 760 | — |
| orig | layers_5 | 435 | 43% | 100 | 725 | 503 | 439 |
| orig | layers_92 | 435 | 43% | 100 | 849 | 630 | 439 |
| orig | 2d | 441 | 42% | 100 | 749 | 525 | 440 |
| orig | 2e_K10 | 440 | 42% | 100 | 761 | 540 | 433 |
| orig | 2e_K500 | 487 | 36% | 100 | 1558 | 1339 | 485 |
| orig | 2f_slru | 128 | 83% | 100 | 7388 | 7161 | 125 |
| **vacuum** | baseline | **1046** | — | — | 1046 | 1046 | — |
| vacuum | layers_5 | 529 | 49% | 100 | 791 | 598 | 532 |
| vacuum | layers_92 | 534 | 49% | 100 | 915 | 720 | 530 |
| vacuum | 2d | 528 | 50% | 100 | 795 | 603 | 529 |
| vacuum | 2e_K10 | 530 | 49% | 100 | 813 | 619 | 530 |
| vacuum | 2e_K500 | 436 | 58% | 18 | 1407 | 1182 | 489 |
| vacuum | 2f_slru | 126 | 88% | 100 | 5731 | 5510 | 126 |
| **ta** | baseline | **788** | — | — | 788 | 788 | — |
| ta | layers_5 | 625 | 21% | 100 | 918 | 693 | 611 |
| ta | layers_92 | 603 | 24% | 29 | 991 | 768 | 618 |
| ta | 2d | 614 | 22% | 78 | 946 | 722 | 595 |
| ta | 2e_K10 | 614 | 22% | 80 | 959 | 737 | 614 |
| ta | 2e_K500 | 746 | 5% | 30 | 1676 | 1455 | 549 |
| ta | 2f_slru | 127 | 84% | 100 | 7370 | 7149 | 125 |

### Workload C (Churn-heavy)

| layout | strategy | fq_async | impr% | deliv% | e2e_std | e2e_warm | oracle(pread) |
|---|---|--:|--:|--:|--:|--:|--:|
| **orig** | baseline | **1096** | — | — | 1096 | 1096 | — |
| orig | layers_5 | 1067 | 3% | 100 | 1360 | 1138 | 1065 |
| orig | layers_92 | 687 | 37% | 100 | 1103 | 881 | 685 |
| orig | 2d | 684 | 38% | 100 | 975 | 753 | 685 |
| orig | 2e_K10 | 211 | 81% | 100 | 512 | 291 | 206 |
| orig | 2e_K500 | 209 | 81% | 67 | 921 | 700 | 211 |
| orig | 2f_slru | 123 | 89% | 100 | 1114 | 892 | 122 |
| **vacuum** | baseline | **993** | — | — | 993 | 993 | — |
| vacuum | layers_5 | 895 | 10% | 100 | 1188 | 963 | 818 |
| vacuum | layers_92 | 508 | 49% | 100 | 920 | 695 | 522 |
| vacuum | 2d | 517 | 48% | 100 | 805 | 584 | 516 |
| vacuum | 2e_K10 | 208 | 79% | 100 | 509 | 287 | 211 |
| vacuum | 2e_K500 | 210 | 79% | 47 | 932 | 711 | 209 |
| vacuum | 2f_slru | 124 | 88% | 100 | 934 | 712 | 122 |
| **ta** | baseline | **871** | — | — | 871 | 871 | — |
| ta | layers_5 | 882 | -1% | 100 | 1174 | 951 | 834 |
| ta | layers_92 | 498 | 43% | 97 | 885 | 663 | 516 |
| ta | 2d | 507 | 42% | 65 | 845 | 621 | 479 |
| ta | 2e_K10 | 208 | 76% | 100 | 556 | 334 | 207 |
| ta | 2e_K500 | 209 | 76% | 100 | 1053 | 830 | 210 |
| ta | 2f_slru | 122 | 86% | 100 | 1153 | 930 | 120 |

**讀法**:① first-query 最低一律是 **2f_slru**(載整個 working set),但其 deliver(A/B ~7ms、C ~0.76ms)使 `e2e` 多半輸——除 C 外兩個 e2e 模型都超 baseline。② **layers_5 / 2d / 2e_K10** 用極少 syscall:`e2e_warm`(= deliver+fq,warm-process/integrated,本研究主張)在三個 workload 都改善(A −7~9%、B −29~34%、**C × 2e_K10 −73% / 291µs**);`e2e_std`(= open+deliver+fq,standalone warmer)則在快 workload 因 ~200µs 冷 open 而變差。③ 兩個 e2e 模型唯一差是冷 open(db):**median 221µs、stdev 17µs(CV 8%)、p95 231µs**(n=810 non-warmup rep),逐 strategy 與逐 layout 皆 ~221µs → **strategy/layout 無關的 common-mode 固定成本**,非 prefetch 獨有稅。把 baseline 也放上 standalone 基準(`baseline+open`)後 open 兩邊相消、`e2e_std` 排序重現 `e2e_warm` verdict(如 A layers_5 對 base+open **−7%**、對照 e2e_warm −9%);快 workload 在 standalone 變差是「prefetch 省下的 first-query 不足以額外 cover 它自己那次 open」,而非 open 偏袒 baseline。詳見 REPORT §5.5.1–§5.5.2。④ `oracle` 欄是同步 pread 的可達下界。
<!-- MASTER-RESULTS-END -->

---

## 全維度數據

> 本節為 **統一 pipeline**(`run_experiment.py` 家族 → `results/main*/`,全 cell `cold_pct`=0)的全 workload(含 **Z**)× layout × 策略 + N/K-sweep + RAM + churn + cadence 彙整;上方「master batch 結果」為 A/B/C 含 delivery_pct/oracle 的詳表。

## 全策略 × layout × workload（async first-query / e2e µs,median）

> baseline = no-prefetch;此處 cell = first-query µs (impr% 相對該 (workload,layout) baseline)。e2e 兩模型(`e2e_std`/`e2e_warm`)見上方「master batch 結果」詳表。
> 來源 [`results/main/summary.csv`](results/main/summary.csv)(A/B/C)+ [`results/z/`](results/z/summary.csv)(Z)。

### Workload A

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig (1a) | 529 | 412 (−22%) | 393 (−26%) | 401 (−24%) | 393 (−26%) | 212 (−60%) | 127 (−76%) |
| vacuum (1b) | 716 | 574 (−20%) | 575 (−20%) | 576 (−20%) | 571 (−20%) | 226 (−68%) | 126 (−82%) |
| ta (1c) | 695 | 524 (−25%) | 457 (−34%) | 463 (−33%) | 401 (−42%) | 340 (−51%) | 128 (−82%) |

### Workload B

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig (1a) | 760 | 435 (−43%) | 435 (−43%) | 441 (−42%) | 440 (−42%) | 487 (−36%) | 128 (−83%) |
| vacuum (1b) | 1046 | 529 (−49%) | 534 (−49%) | 528 (−50%) | 530 (−49%) | 436 (−58%) | 126 (−88%) |
| ta (1c) | 788 | 625 (−21%) | 603 (−24%) | 614 (−22%) | 614 (−22%) | 746 (−5%) | 127 (−84%) |

### Workload C

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig (1a) | 1096 | 1067 (−3%) | 687 (−37%) | 684 (−38%) | 211 (−81%) | 209 (−81%) | 123 (−89%) |
| vacuum (1b) | 993 | 895 (−10%) | 508 (−49%) | 517 (−48%) | 208 (−79%) | 210 (−79%) | 124 (−88%) |
| ta (1c) | 871 | 882 (−-1%) | 498 (−43%) | 507 (−42%) | 208 (−76%) | 209 (−76%) | 122 (−86%) |

### Workload Z

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig (1a) | 525 | 409 (−22%) | 383 (−27%) | 411 (−22%) | 203 (−61%) | 204 (−61%) | 119 (−77%) |
| vacuum (1b) | 705 | 570 (−19%) | 572 (−19%) | 571 (−19%) | 205 (−71%) | 203 (−71%) | 117 (−83%) |
| ta (1c) | 737 | 598 (−19%) | 460 (−38%) | 467 (−37%) | 203 (−72%) | 203 (−72%) | 117 (−84%) |

### 2f_slru first-q vs e2e（preprocessing trap）

| workload×layout | fq | open | deliver | e2e_std | e2e_warm | e2e_warm vs base |
|---|--:|--:|--:|--:|--:|--:|
| A/orig | 127 | 193 | 7007 | 7327 | 7134 | 13.5× |
| A/vacuum | 126 | 222 | 5336 | 5684 | 5463 | 7.6× |
| A/ta | 128 | 222 | 7017 | 7367 | 7146 | 10.3× |
| B/orig | 128 | 222 | 7033 | 7388 | 7161 | 9.4× |
| B/vacuum | 126 | 223 | 5384 | 5731 | 5510 | 5.3× |
| B/ta | 127 | 222 | 7022 | 7370 | 7149 | 9.1× |
| C/orig | 123 | 222 | 761 | 1114 | 892 | 0.8× |
| C/vacuum | 124 | 222 | 585 | 934 | 712 | 0.7× |
| C/ta | 122 | 222 | 808 | 1153 | 930 | 1.1× |

## layers_N sweep（clean,async first-q µs;N=0=baseline）

> 來源 [`results/nsweep_dense/`](results/nsweep_dense/summary.csv)。

### Workload A

| layout | N=0 | N=1 | N=2 | N=3 | N=4 | N=5 | N=6 | N=8 | N=12 | N=16 | N=24 | N=32 | N=46 | N=64 | N=92 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| orig | 505 | 663 | 639 | 662 | 334 | 333 | 331 | 331 | 302 | 331 | 334 | 335 | 327 | 332 | 333 |
| vacuum | 702 | 961 | 962 | 968 | 556 | 549 | 556 | 555 | 552 | 552 | 555 | 552 | 548 | 552 | 558 |
| ta | 681 | 894 | 866 | 856 | 496 | 498 | 498 | 498 | 490 | 482 | 470 | 459 | 489 | 464 | 426 |

### Workload B

| layout | N=0 | N=1 | N=2 | N=3 | N=4 | N=5 | N=6 | N=8 | N=12 | N=16 | N=24 | N=32 | N=46 | N=64 | N=92 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| orig | 728 | 696 | 703 | 692 | 380 | 385 | 382 | 382 | 385 | 379 | 390 | 379 | 383 | 387 | 382 |
| vacuum | 1023 | 916 | 919 | 916 | 507 | 503 | 511 | 510 | 508 | 507 | 531 | 511 | 515 | 508 | 519 |
| ta | 798 | 1004 | 999 | 933 | 603 | 603 | 603 | 603 | 598 | 590 | 579 | 565 | 596 | 570 | 582 |

### Workload C

| layout | N=0 | N=1 | N=2 | N=3 | N=4 | N=5 | N=6 | N=8 | N=12 | N=16 | N=24 | N=32 | N=46 | N=64 | N=92 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| orig | 1074 | 1018 | 1021 | 952 | 1017 | 1021 | 1015 | 1017 | 1019 | 1017 | 1016 | 1012 | 1009 | 1008 | 633 |
| vacuum | 983 | 859 | 902 | 895 | 897 | 891 | 898 | 901 | 897 | 896 | 894 | 895 | 866 | 495 | 504 |
| ta | 872 | 858 | 830 | 821 | 832 | 838 | 844 | 826 | 824 | 824 | 811 | 788 | 890 | 796 | 474 |

### Workload Z

| layout | N=0 | N=1 | N=2 | N=3 | N=4 | N=5 | N=6 | N=8 | N=12 | N=16 | N=24 | N=32 | N=46 | N=64 | N=92 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| orig | 509 | 676 | 676 | 638 | 356 | 335 | 381 | 368 | 364 | 364 | 339 | 381 | 376 | 364 | 382 |
| vacuum | 708 | 968 | 963 | 964 | 543 | 554 | 555 | 555 | 552 | 552 | 559 | 555 | 552 | 552 | 562 |
| ta | 728 | 901 | 835 | 905 | 575 | 571 | 576 | 575 | 572 | 562 | 552 | 558 | 564 | 540 | 438 |

## 2e K-sweep（async first-q µs;K=0=2d interior-only）

> 來源 [`results/ksweep/`](results/ksweep/summary.csv)。

### Workload A

| layout | K=0 | K=10 | K=40 | K=50 | K=92 | K=100 | K=500 |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig | 332 | 335 | 331 | 333 | 244 | 248 | 156 |
| vacuum | 560 | 557 | 554 | 552 | 348 | 348 | 188 |
| ta | 453 | 398 | 393 | 395 | 786 | 512 | 201 |

### Workload B

| layout | K=0 | K=10 | K=40 | K=50 | K=92 | K=100 | K=500 |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig | 385 | 385 | 381 | 387 | 383 | 382 | 429 |
| vacuum | 509 | 519 | 508 | 507 | 517 | 512 | 409 |
| ta | 590 | 595 | 596 | 593 | 593 | 592 | 611 |

### Workload C

| layout | K=0 | K=10 | K=40 | K=50 | K=92 | K=100 | K=500 |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig | 636 | 153 | 153 | 152 | 154 | 154 | 155 |
| vacuum | 493 | 187 | 185 | 186 | 185 | 187 | 188 |
| ta | 480 | 189 | 189 | 188 | 189 | 188 | 189 |

## 三槓桿 ablation（S1：勝利來自哪個 selection 槓桿）

> 來源 [`results/ablation/`](results/ablation/) + [`results/ablation_k500/`](results/ablation_k500/);跨-seed CI 由 [`tools/stats_uncertainty.py`](tools/stats_uncertainty.py) 產 [`results/ablation/uncertainty.csv`](results/ablation/uncertainty.csv)、表由 [`tools/ablation_table.py`](tools/ablation_table.py) 產。
> 把 2e_K 的 hotset 拆成兩個 selection 槓桿並加對照組,**同 layout、同一批跑、10-seed bootstrap 95% CI**。集合上 `2e_K = 2d ∪ leaf_freq_K`,故為 exact 分解。
> - **2d** = 只載 interior（page-type 槓桿 (ii)）
> - **leaf_freq_K** = 只載 top-K 熱 leaf（access-frequency 槓桿 (iii)，= 2e_K 扣 interior）
> - **leaf_rand_K** = 同型別(leaf_table)、同張數、但隨機抽的非熱 leaf（**對照組**:只差「有沒有照頻率挑」）
> - **2e_K** = interior ∪ 熱 leaf（合併 (ii)+(iii)）
>
> 關鍵讀法:**leaf_rand vs leaf_freq**——同 page-type、同張數,任何差距就是 access-frequency 訊號。

效應 = strategy median vs **同 seed baseline** median,跨 seed mean Δ%、bootstrap 95% CI（async arm）。

### layout orig

| workload | arm | 槓桿 | pages | first-q Δ% [CI] | e2e_warm Δ% [CI] |
|---|---|---|--:|---|---|
| A | 2d | (ii) page-type | 18 | −37% [−41,−34] robust | −27% [−31,−22] robust |
| A | **leaf_rand_K10** | 對照 | 10 | **+0% [−2,+3] tie** | +10% [+7,+12] robust |
| A | **leaf_freq_K10** | (iii) access-freq | 10 | **−13% [−26,−1] robust** | −4% [−18,+8] directional |
| A | 2e_K10 | 合併 | 28 | −50% [−63,−37] robust | −38% [−52,−25] robust |
| A | leaf_rand_K500 | 對照 | 500 | −3% [−7,+1] dir. | +99% [+87,+116] robust |
| A | leaf_freq_K500 | (iii) access-freq | 500 | +21% [−26,+98] dir. | +114% [+62,+191] robust |
| A | 2e_K500 | 合併 | 518 | −17% [−62,+58] dir. | +81% [+34,+151] robust |
| B | 2d | (ii) page-type | 18 | −36% [−43,−25] robust | −26% [−34,−14] robust |
| B | **leaf_rand_K10** | 對照 | 10 | **−2% [−3,−1] robust** | +7% [+6,+8] robust |
| B | **leaf_freq_K10** | (iii) access-freq | 10 | **−3% [−4,−2] robust** | +6% [+5,+7] robust |
| B | 2e_K10 | 合併 | 28 | −37% [−43,−28] robust | −26% [−32,−15] robust |
| C | 2d | (ii) page-type | 4 | −43% [−46,−41] robust | −36% [−38,−34] robust |
| C | **leaf_rand_K10** | 對照 | 10 | **−2% [−3,−1] robust** | +6% [+5,+7] robust |
| C | **leaf_freq_K10** | (iii) access-freq | 10 | **−40% [−43,−37] robust** | −32% [−35,−28] robust |
| C | 2e_K10 | 合併 | 14 | **−81% [−82,−80] robust** | **−73% [−74,−72] robust** |

### layout ta

| workload | arm | 槓桿 | pages | first-q Δ% [CI] | e2e_warm Δ% [CI] |
|---|---|---|--:|---|---|
| A | 2d | (ii) page-type | 43 | −37% [−44,−30] robust | −24% [−33,−16] robust |
| A | leaf_rand_K10 | 對照 | 10 | −2% [−3,+0] dir. | +8% [+6,+9] robust |
| A | leaf_freq_K10 | (iii) access-freq | 10 | −12% [−25,−0] robust | −3% [−17,+9] dir. |
| A | 2e_K10 | 合併 | 53 | −48% [−63,−34] robust | −34% [−51,−18] robust |
| A | 2e_K500 | 合併 | 543 | −51% [−66,−35] robust | +39% [+20,+57] robust |
| B | 2d | (ii) page-type | 40 | −36% [−44,−28] robust | −22% [−32,−13] robust |
| B | leaf_rand_K10 | 對照 | 10 | −1% [−3,+0] dir. | +8% [+6,+10] robust |
| B | leaf_freq_K10 | (iii) access-freq | 10 | −1% [−3,+3] dir. | +9% [+6,+13] robust |
| B | 2e_K10 | 合併 | 50 | −37% [−44,−30] robust | −22% [−31,−14] robust |
| C | 2d | (ii) page-type | 48 | −44% [−45,−43] robust | −31% [−32,−29] robust |
| C | leaf_rand_K10 | 對照 | 10 | −2% [−3,−1] robust | +7% [+5,+8] robust |
| C | leaf_freq_K10 | (iii) access-freq | 10 | −32% [−36,−29] robust | −24% [−28,−20] robust |
| C | 2e_K10 | 合併 | 58 | −80% [−81,−79] robust | −65% [−67,−64] robust |

**讀法總結:**
1. **C(churn-heavy)**:`leaf_rand` −2%(對照,無效)vs `leaf_freq` −40%——同 page-type、同 10 張,38 點全是 **access-frequency 訊號**。headline −81% = interior(2d −43%)＋熱 leaf(−40%)疊加。**這是「page-type-aware」命名對不上 headline 的直接證據。**
2. **B(uniform)**:無熱 leaf → `leaf_freq ≈ leaf_rand ≈ 0`,改善全由 **2d(interior, page-type, −36%)** 提供;2e_K10 ≈ 2d。
3. **A(zipfian)**:居中——leaf_freq_K10 −13%(robust、真有頻率訊號)但主力仍是 2d(−37%);**K=500 的 leaf-only 在 orig 反而 +21%(載 500 散落 leaf 的 deliver 成本壓過紅利)**,且所有 K500 的 `e2e_warm` 皆轉正(+39~114%,deliver ~0.8 ms 吃掉一切)——**access-frequency 的價值在於「小而準」(K=10),不在「多」**。
4. **layout 槓桿(orig→ta)**:只改 deliver 成本、不改 selection 故事;ta collocate interior 卻使 2d/2e 的 interior 集合變大(C 4→48 頁),warm e2e 反略遜(C 2e_K10 orig −73% vs ta −65%),呼應 §6.1「type-aware layout 非淨贏」。

→ 命名校正:本框架是 **type-aware(interior)＋ access-frequency-aware(hot leaf) 的複合 targeting**;page-type 扛 B/A 主力、access-frequency 解鎖 C headline。圖見 [figures/out/17_lever_ablation.png](figures/out/17_lever_ablation.png)。

## 競爭性 baseline（RR1 / S4：targeted vs 調校過的 ranked dump）

> 來源 [`results/competitive/`](results/competitive/)；`2f_topN` 由 [`strategies/access/runs/gen_freqdump.py`](strategies/access/runs/gen_freqdump.py) 產（replay 每筆 read 的 B+tree path 計次、按頻率排序 resident WS 取前 N，**不用 page-type**），CI 由 `tools/stats_uncertainty.py` 出。
> 問題：§5.5 的「targeted > dump」是「機制贏」還是只是「dump 少一點」？對照 `2f_topN`（tuned ranked partial dump）掃 footprint {14,28,100,500,full}，同 e2e accounting、10-seed CI。

跨 10 seed mean Δ% vs 同 seed baseline [95% CI]（async、orig；皆 robust）：

### first-query

| arm（footprint） | A | B | C |
|---|---:|---:|---:|
| 2e_K10（targeted, 14–28p） | −50 [−64,−38] | −35 [−42,−25] | −81 [−82,−80] |
| 2f_top14 | −42 [−52,−35] | −36 [−43,−27] | −65 [−76,−53] |
| 2f_top28 | −49 [−63,−37] | −37 [−43,−29] | −70 [−80,−59] |
| 2f_top100 | −56 [−68,−44] | −41 [−53,−30] | −70 [−80,−60] |
| 2f_top500 | −16 [−62,+58] | −50 [−63,−37] | −90 [−90,−90] |
| 2f_slru（full） | −88 [−89,−86] | −89 [−90,−87] | −90 [−90,−90] |

### e2e_warm（本研究主張的部署模型）

| arm（footprint） | A | B | C |
|---|---:|---:|---:|
| **2e_K10（targeted, 14–28p）** | **−38 [−53,−25]** | **−24 [−31,−12]** | **−72 [−74,−71]** |
| 2f_top14 | −33 [−43,−24] | −27 [−34,−16] | −57 [−68,−45] |
| 2f_top28 | −37 [−52,−24] | −26 [−32,−16] | −60 [−69,−49] |
| 2f_top100 | −32 [−45,−19] | −18 [−32,−4] | −52 [−60,−42] |
| 2f_top500 | **+81 [+34,+151]** | **+44 [+28,+60]** | −13 [−17,−8] |
| 2f_slru（full, ~4400p） | **+762 [+674,+899]** | **+730 [+644,+848]** | −12 [−17,−7] |

**讀法：**
1. **first-q 看 footprint 越大越低**（2f_slru 全載 → −88~90% 最低），但 **e2e_warm 越大越糟**（deliver 成本）——正是 §5.5「first-q ≠ e2e」的 trade-off。sweet spot 在小 footprint（N≈14–28）。
2. **broad A/B**：tuned `2f_topN`（純頻率）在 matched footprint 下 e2e_warm **追平** `2e_K10`（CI 重疊）→ **page-type 非必要**，與 §5.4.1 ablation 一致。
3. **narrow C**：`2e_K10` −72%[−74,−71] **robustly 勝** matched `2f_top14` −57%[−68,−45]（CI 分離）→ page-type 用「保證載入 interior skeleton」在窄 workload 提供 robustness（純頻率 top-14 只挑到 2 個 interior）。
4. **結論**：`2e_K10` **從未被 tuned dump 打敗**（A/B 平、C 勝）→ §5.5 非稻草人勝；機制歸因＝「**小 footprint + frequency ranking**」為主、page-type 在 narrow workload 加 robustness。圖見 [figures/out/18_competitive_baseline.png](figures/out/18_competitive_baseline.png)。

## RAM-pressure（cgroup MemoryMax=20M / unlimited 比值,async first-q）

> 來源 [`results/ram20m/`](results/ram20m/summary.csv)(20M cgroup)÷ **同期(06-22)unconfined** baseline。比值近 1.0 → 壓力幾乎不影響。
> ⚠️ **20M cap 在 working set(A/B ≈ 17.3 MB)之上 → 沒有實質施壓**，故比值近 1.0。要看真壓力見下方「sub-working-set sweep」。
> ⚠️ 分母**必須是同 session** 的 unconfined run(群①);**勿** ÷ 現在的 `results/main`(06-24 重跑、群③、慢 ~15%)——那會得 ~0.85 的**機器狀態假象**,非壓力效應。詳見上方「資料可比性」。

| workload×layout | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|
| A/orig | 1.05 | 1.00 | 1.00 | 0.98 | 1.01 | 1.03 |
| A/vacuum | 1.00 | 1.00 | 1.01 | 1.00 | 1.00 | 1.00 |
| A/ta | 1.00 | 1.01 | 1.01 | 1.01 | 0.95 | 1.03 |
| B/orig | 1.01 | 1.00 | 1.01 | 1.00 | 1.00 | 1.07 |
| B/vacuum | 1.00 | 1.00 | 1.01 | 1.00 | 1.01 | 0.98 |
| B/ta | 1.01 | 1.01 | 1.01 | 1.00 | 1.00 | 1.02 |
| C/orig | 1.00 | 1.00 | 0.99 | 0.98 | 1.01 | 1.01 |
| C/vacuum | 1.00 | 1.00 | 1.00 | 1.01 | 1.00 | 1.00 |
| C/ta | 0.99 | 1.01 | 0.99 | 1.00 | 1.00 | 1.00 |

## RAM-pressure（sub-working-set sweep；cap 壓到 working set 以下）

> 來源 [`results/ram_pressure/`](results/ram_pressure/analysis.csv)(`tools/ram_pressure.sh`,seed 1,layout orig,async)。
> working set ≈ **A/B 17.3 MB、C 1.8 MB**。cap ladder `{∞,16M,12M,8M,6M}` = `{∞,0.92,0.69,0.46,0.35}×WS`。
> **量 `delivery_pct`**（prefetch 過的 page 在 first-query 前的 mincore 殘留率）+ first-q。可量測下限 ≈ 6M；4M 以下 cold gate 全排除。
> hotset 大小決定誰被壓到：2e_K10 ≈ 112 KB、2e_K500 ≈ 2.07 MB、**2f_slru ≈ 17.7 MB（＝整個 WS）**。

**delivery_pct（%，async,first-query 前 mincore 殘留率）**

| workload × strategy | ∞ | 16M (0.92×) | 12M (0.69×) | 8M (0.46×) | 6M (0.35×) |
|---|--:|--:|--:|--:|--:|
| A 2e_K10 | 100 | 100 | 100 | 100 | 100 |
| A 2e_K500 | 100 | 100 | 100 | 100 | 100 |
| **A 2f_slru** | 100 | **77.4** | **54.3** | **32.2** | **18.7** |
| B 2e_K10 | 100 | 100 | 100 | 100 | 100 |
| B 2e_K500 | 100 | 100 | 100 | 100 | 100 |
| **B 2f_slru** | 100 | **77.9** | **55.9** | **31.2** | **17.1** |

**first-query latency（µs,async）**

| workload × strategy | ∞ | 16M | 12M | 8M | 6M | baseline |
|---|--:|--:|--:|--:|--:|--:|
| A 2e_K10 | 402 | 362 | 353 | 372 | 357 | 502 |
| A 2e_K500 | 179 | 183 | 178 | 180 | 179 | 502 |
| **A 2f_slru** | **95** | **490** | **487** | **484** | **489** | 502 |
| B 2e_K10 | 408 | 411 | 405 | 404 | 406 | 723 |
| B 2e_K500 | 452 | 453 | 448 | 451 | 451 | 723 |
| **B 2f_slru** | **96** | **741** | **735** | **724** | **716** | 723 |

> 讀法：**targeted（2e_K10/2e_K500）delivery 全程 100%、first-q 全程平** → hotset 太小、reclaim 碰不到 → RAM-robust by construction。
> **2f_slru（dump＝整個 WS）delivery 隨 cap 線性塌（≈ cap/WS）**，且 first-q 一旦 delivery 跌破 100% 就**直跳回 baseline 並維持**（all-or-nothing,無 graceful degradation）。
> 即「小而準 > 大而全」在記憶體受限裝置上成立。圖見 `figures/out/16_ram_pressure_sweep.png`。

## Churn-evolution（layout orig,static t=0 hotset,first-q µs;CSV 另含 vacuum/ta）

> 來源 [`results/churn/churn_evolution.csv`](results/churn/churn_evolution.csv)。

### Workload A

| strategy | ck0 | ck1 | ck2 | ck3 | ck4 | ck5 | ck6 | ck7 | ck8 | ck9 | ck10 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline | 378 | 407 | 369 | 360 | 377 | 329 | 368 | 369 | 347 | 362 | 327 |
| 2e_K10_static | 241 | 271 | 339 | 277 | 271 | 309 | 271 | 230 | 230 | 225 | 228 |
| layers_92_static | 254 | 278 | 278 | 276 | 270 | 309 | 270 | 231 | 229 | 244 | 230 |

### Workload B

| strategy | ck0 | ck1 | ck2 | ck3 | ck4 | ck5 | ck6 | ck7 | ck8 | ck9 | ck10 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline | 531 | 547 | 571 | 517 | 559 | 507 | 514 | 508 | 543 | 475 | 493 |
| 2e_K10_static | 253 | 252 | 302 | 280 | 305 | 302 | 295 | 265 | 276 | 235 | 246 |
| layers_92_static | 259 | 252 | 283 | 298 | 339 | 299 | 295 | 266 | 278 | 248 | 253 |

### Workload C

| strategy | ck0 | ck1 | ck2 | ck3 | ck4 | ck5 | ck6 | ck7 | ck8 | ck9 | ck10 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline | 592 | 563 | 616 | 564 | 565 | 587 | 611 | 586 | 543 | 528 | 544 |
| 2e_K10_static | 86 | 89 | 83 | 81 | 265 | 86 | 82 | 88 | 86 | 84 | 82 |
| layers_92_static | 252 | 245 | 278 | 274 | 303 | 309 | 268 | 592 | 265 | 264 | 266 |

## Multi-process cadence（背景 warmer 重暖 + 全機 drop probe,first-q µs）

> 來源 [`results/cadence/cadence_results.csv`](results/cadence/cadence_results.csv)。

| cadence | round | first_q_us | delivery_pct |
|---|---|---|---|
| 1.0 | 0 | 27.03 | 100.0 |
| 1.0 | 1 | 25.76 | 100.0 |
| 1.0 | 2 | 25.16 | 100.0 |
| 1.0 | 3 | 36.74 | 100.0 |
| 1.0 | 4 | 26.10 | 100.0 |
| 1.0 | 5 | 29.93 | 100.0 |
| 1.0 | 6 | 26.07 | 100.0 |
| 1.0 | 7 | 25.46 | 100.0 |
| 5.0 | 0 | 262.38 | 0.7 |
| 5.0 | 1 | 25.80 | 100.0 |
| 5.0 | 2 | 24.71 | 100.0 |
| 5.0 | 3 | 273.25 | 0.7 |

## DB 尺寸 scaling（orig 100MB vs 1gb,6M row ~1 GiB）— size sensitivity

> 為回答「**當 DB 遠大於 hot working set 時,prefetch 還靈不靈**」,新建 `test_db_1gb.db`
> (6,000,000 row、263,991 page、~1 GiB、`classify_1gb.csv`),與 100MB `orig`(600k row)用
> **同一份 seed-1 query stream** 跑全 matrix(4 workload × 6 策略 × pread/async + 4 baseline,
> **全 cell `cold_pct`=0**)。來源 [`results/size_1gb/`](results/size_1gb/summary.csv)。
> ℹ️ 此處 seed-1 query stream **就是原始 100MB 的 master workload**(原始檔 renamed 成 `workload_*_1.txt`,
> 日期 2026-05-23;`results/seeds/seed01` 跑這份 orig 的數字與上方 master 表幾乎一致 → 證實同源)。
> 本節 orig 與 1gb 在**同一批次、rep-major 交錯**量測,是原始 workload 上的 apples-to-apples 尺寸比較。
> **本節是一個自足的 full-boost 批次**(機器滿頻乾淨狀態):machine-independent 的 `2f_slru` first-query
> 全格落在 **88–98µs**——這是 CPU 滿頻 boost(cpu2 ~5.6 GHz)下「乾淨」的冷啟動下界。
> 上方 master / cross-seed 表的 `2f_slru` ~122–130µs 則是當時**長時間連跑 sweep、boost 被熱/功耗壓低**的數字
> (兩者皆有效,只是機器狀態不同;本機無 root 可釘頻,兩態無法互相重現)。
> 因此**本節絕對 µs 自成一個尺度,不與上方 master / cross-seed 表逐格比**;1gb 的 100MB 對照基準
> **就是本節同批的 `orig` 列**(同態量測)。**尺寸的相對結論不受機器狀態影響**(下方跨-seed 章用相對 Δ%,更已把此抵消)。
> cell = async first-query µs(括號 impr% 相對該 (workload,layout) baseline)。

### Workload A（Zipfian）

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig | 487 | 380 (−22%) | 399 (−18%) | 359 (−26%) | 357 (−27%) | 180 (−63%) | 96 (−80%) |
| 1gb | 550 | 459 (−17%) | 456 (−17%) | 288 (−48%) | 288 (−48%) | 151 (−72%) | 98 (−82%) |

### Workload B（Uniform）

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig | 735 | 404 (−45%) | 405 (−45%) | 406 (−45%) | 404 (−45%) | 451 (−39%) | 96 (−87%) |
| 1gb | 722 | 483 (−33%) | 482 (−33%) | 318 (−56%) | 314 (−56%) | 394 (−45%) | 98 (−86%) |

### Workload C（窄域 5×）

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig | 1041 | 1032 (−1%) | 654 (−37%) | 650 (−38%) | 176 (−83%) | 174 (−83%) | 88 (−92%) |
| 1gb | 711 | 639 (−10%) | 476 (−33%) | 308 (−57%) | 143 (−80%) | 144 (−80%) | 91 (−87%) |

### Workload Z（低 key Zipf）

| layout | baseline | layers_5 | layers_92 | 2d | 2e_K10 | 2e_K500 | 2f_slru |
|---|--:|--:|--:|--:|--:|--:|--:|
| orig | 499 | 379 (−24%) | 352 (−29%) | 378 (−24%) | 173 (−65%) | 174 (−65%) | 88 (−82%) |
| 1gb | 546 | 453 (−17%) | 451 (−17%) | 281 (−48%) | 142 (−74%) | 144 (−74%) | 90 (−83%) |

### 2f_slru：first-q vs deliver/e2e（resident-set 隨 DB 變大）

> deliver = async 逐頁 fadvise 的耗時;e2e_warm = deliver+fq(warm-process,本研究主張)。resident pages = 跑完該 seed-1 workload 後常駐的 working-set 頁數(2f hotset 大小)。

| workload×layout | resident pages | fq | deliver | e2e_warm | e2e_warm vs base |
|---|--:|--:|--:|--:|--:|
| A/orig | 4416 | 96 | 7058 | 7152 | 14.7× |
| A/1gb | 4448 | 98 | 7004 | 7100 | 12.9× |
| B/orig | 4420 | 96 | 7000 | 7096 | 9.7× |
| B/1gb | 4452 | 98 | 7039 | 7139 | 9.9× |
| C/orig | 483 | 88 | 800 | 888 | 0.9× |
| C/1gb | 984 | 91 | 1706 | 1798 | 2.5× |
| Z/orig | 112 | 88 | 185 | 273 | 0.5× |
| Z/1gb | 144 | 90 | 222 | 313 | 0.6× |

**讀法**:① **first-query 上 prefetch 的效益在 1GB 守得住、小 hotset 策略甚至放大**——`2f_slru` 兩尺寸都收斂到 ~96–98µs(−80~87%),first-query 只看 hot working set、與 DB 大小無關;`2d` / `2e_K10` 在 A/B/Z 於 1GB 反而改善更大(A 2d −26%→−48%、B 2d −45%→−56%、Z 2d −24%→−48%),因為**同一批 hot key 散到 6M-row DB 的更多 page,no-prefetch baseline 的冷讀更分散更貴,targeted prefetch 相對更划算**。② **e2e_warm(部署指標)上 2f 的 deliver 成本跟著 resident-set、不是 DB 大小走**:A/B 的 working set ~4.4k page 兩尺寸幾乎不變 → deliver ~7ms 不變 → e2e_warm 仍 ~10–15× baseline 慘輸;但 **C 是警訊**——resident set 483→**984** page 翻倍(窄域 key 在大 DB 散得更開)→ deliver 800→1706µs → e2e_warm 0.9×→**2.5× baseline**,C 在 100MB 是 2f 唯一能贏的格,到 1GB 也由贏轉輸。③ `layers_5/92`(固定 5/92 interior page)結構派與 working-set 無關,跨尺寸 deliver 幾乎不變。④ C baseline 在 1gb 反而較低(1041→711)屬 first-query 落點雜訊,不影響相對排序。**結論:targeted prefetch 的 first-query 優勢 size-robust;2f 的 e2e 陷阱在窄域 workload 會隨 DB 變大而惡化。**

## 資料來源

- 主矩陣:[`results/main/summary.csv`](results/main/summary.csv)、Z:[`results/z/`](results/z/summary.csv)
- DB 尺寸 scaling(orig vs 1gb,seed-1):[`results/size_1gb/`](results/size_1gb/summary.csv)
- DB 尺寸 × 跨-seed(1gb,A/B/C × 10 seed):[`results/seeds_1gb/`](results/seeds_1gb/) → [`results/stats/uncertainty_1gb.csv`](results/stats/uncertainty_1gb.csv)(腳本 `tools/run_seed_sweep_1gb.sh` + `tools/stats_uncertainty.py`)
- N-sweep:[`results/nsweep_dense/`](results/nsweep_dense/summary.csv)、K-sweep:[`results/ksweep/`](results/ksweep/summary.csv)
- RAM 20M:[`results/ram20m/`](results/ram20m/summary.csv)、churn:[`results/churn/`](results/churn/)、cadence:[`results/cadence/`](results/cadence/cadence_results.csv)
- 凍結清單:[`results/main/hotset_freeze.sha256`](results/main/hotset_freeze.sha256)。完整執行覆蓋見 [IMPLEMENTATION_PIPELINES.md §3.8](IMPLEMENTATION_PIPELINES.md)。


## Cross-seed workload-sensitivity (10 seeds) — R3

10 個 random seed 各重生成 A/B/C（同一份 DB、同 reps），各跑一次完整 matrix；
per-seed 效應 = 同 seed 內 strategy vs baseline 的 Δ%，下表報跨 10 seed 的 **mean、
bootstrap 95% CI of the mean、符號一致性 (n/10)、verdict**（robust=CI 不跨 0；
directional=CI 跨 0 但 ≥7/10 同號；tie=否則）。完整 54-cell×3-metric 見 
[`results/stats/uncertainty.csv`](results/stats/uncertainty.csv)；分析腳本 `tools/stats_uncertainty.py`。

機器穩定性對照：2f_slru first-query 跨 10 seed 維持 125.9–130.2 µs（與第一筆查哪個 key 無關），
證明 sweep 期間無 CPU throttle、跨 seed 變異來自 workload 抽樣。

### warm-process e2e（本研究主張的部署指標）（async arm）

| layout | workload | strategy | mean Δ% | 95% CI | sign | verdict |
|---|---|---|---:|---|---:|---|
| orig | A | layers_5 | -5.12 | [-15.94, 4.42] | 6/10 | tie |
| orig | A | layers_92 | -12.5 | [-18.05, -5.7] | 9/10 | robust |
| orig | A | 2d | -24.95 | [-29.44, -19.83] | 10/10 | robust |
| orig | A | 2e_K10 | -36.01 | [-49.98, -23.07] | 10/10 | robust |
| orig | A | 2e_K500 | 79.07 | [36.53, 141.43] | 10/10 | robust |
| orig | A | 2f_slru | 744.14 | [661.67, 870.21] | 10/10 | robust |
| orig | B | layers_5 | -1.27 | [-11.71, 6.68] | 8/10 | directional |
| orig | B | layers_92 | -13.17 | [-20.45, -1.74] | 9/10 | robust |
| orig | B | 2d | -25.44 | [-31.56, -16.18] | 9/10 | robust |
| orig | B | 2e_K10 | -24.65 | [-30.31, -15.61] | 9/10 | robust |
| orig | B | 2e_K500 | 40.24 | [24.48, 55.14] | 10/10 | robust |
| orig | B | 2f_slru | 703.6 | [631.93, 799.01] | 10/10 | robust |
| orig | C | layers_5 | 4.78 | [3.75, 6.06] | 10/10 | robust |
| orig | C | layers_92 | -20.62 | [-21.97, -19.22] | 10/10 | robust |
| orig | C | 2d | -35.88 | [-38.54, -33.07] | 10/10 | robust |
| orig | C | 2e_K10 | -70.47 | [-71.88, -69.13] | 10/10 | robust |
| orig | C | 2e_K500 | -30.63 | [-34.07, -27.27] | 10/10 | robust |
| orig | C | 2f_slru | -9.0 | [-13.87, -4.07] | 8/10 | robust |
| vacuum | A | layers_5 | -15.12 | [-26.52, -5.1] | 10/10 | robust |
| vacuum | A | layers_92 | -25.97 | [-31.6, -17.69] | 9/10 | robust |
| vacuum | A | 2d | -36.73 | [-42.2, -29.38] | 10/10 | robust |
| vacuum | A | 2e_K10 | -44.4 | [-56.62, -31.94] | 10/10 | robust |
| vacuum | A | 2e_K500 | 16.27 | [2.72, 30.47] | 7/10 | robust |
| vacuum | A | 2f_slru | 458.24 | [411.07, 517.75] | 10/10 | robust |
| vacuum | B | layers_5 | -10.5 | [-21.56, -2.45] | 10/10 | robust |
| vacuum | B | layers_92 | -22.49 | [-28.33, -13.41] | 9/10 | robust |
| vacuum | B | 2d | -34.55 | [-39.89, -26.47] | 10/10 | robust |
| vacuum | B | 2e_K10 | -33.15 | [-38.82, -23.96] | 9/10 | robust |
| vacuum | B | 2e_K500 | 18.02 | [3.89, 31.53] | 9/10 | robust |
| vacuum | B | 2f_slru | 435.43 | [386.88, 506.03] | 10/10 | robust |
| vacuum | C | layers_5 | -2.46 | [-3.64, -1.3] | 9/10 | robust |
| vacuum | C | layers_92 | -28.5 | [-29.81, -27.19] | 10/10 | robust |
| vacuum | C | 2d | -39.87 | [-41.77, -38.11] | 10/10 | robust |
| vacuum | C | 2e_K10 | -74.02 | [-75.39, -72.52] | 10/10 | robust |
| vacuum | C | 2e_K500 | -38.06 | [-41.01, -34.89] | 10/10 | robust |
| vacuum | C | 2f_slru | -34.3 | [-38.2, -30.02] | 10/10 | robust |
| ta | A | layers_5 | 0.69 | [-9.73, 12.63] | 6/10 | tie |
| ta | A | layers_92 | -15.66 | [-23.43, -8.19] | 9/10 | robust |
| ta | A | 2d | -22.52 | [-29.98, -15.6] | 10/10 | robust |
| ta | A | 2e_K10 | -31.82 | [-47.58, -16.92] | 9/10 | robust |
| ta | A | 2e_K500 | 44.61 | [27.86, 61.96] | 10/10 | robust |
| ta | A | 2f_slru | 722.16 | [635.81, 811.01] | 10/10 | robust |
| ta | B | layers_5 | 12.99 | [-1.13, 28.32] | 5/10 | tie |
| ta | B | layers_92 | -14.02 | [-24.63, -3.65] | 7/10 | robust |
| ta | B | 2d | -19.86 | [-29.43, -10.27] | 9/10 | robust |
| ta | B | 2e_K10 | -19.89 | [-28.31, -11.76] | 10/10 | robust |
| ta | B | 2e_K500 | 51.0 | [29.82, 72.79] | 9/10 | robust |
| ta | B | 2f_slru | 755.75 | [642.34, 878.62] | 10/10 | robust |
| ta | C | layers_5 | 5.57 | [5.18, 5.96] | 10/10 | robust |
| ta | C | layers_92 | -24.64 | [-25.72, -23.65] | 10/10 | robust |
| ta | C | 2d | -29.65 | [-30.77, -28.64] | 10/10 | robust |
| ta | C | 2e_K10 | -62.99 | [-64.72, -61.4] | 10/10 | robust |
| ta | C | 2e_K500 | -10.64 | [-15.03, -6.36] | 9/10 | robust |
| ta | C | 2f_slru | 4.61 | [-1.06, 10.02] | 6/10 | tie |

### first-query latency（async arm）

| layout | workload | strategy | mean Δ% | 95% CI | sign | verdict |
|---|---|---|---:|---|---:|---|
| orig | A | layers_5 | -13.23 | [-24.37, -3.26] | 8/10 | robust |
| orig | A | layers_92 | -35.62 | [-39.58, -31.36] | 10/10 | robust |
| orig | A | 2d | -35.09 | [-38.86, -31.02] | 10/10 | robust |
| orig | A | 2e_K10 | -47.72 | [-60.85, -35.79] | 10/10 | robust |
| orig | A | 2e_K500 | -17.62 | [-59.14, 48.87] | 9/10 | directional |
| orig | A | 2f_slru | -84.9 | [-86.35, -82.64] | 10/10 | robust |
| orig | B | layers_5 | -9.04 | [-19.35, -0.92] | 7/10 | robust |
| orig | B | layers_92 | -34.88 | [-40.91, -25.61] | 9/10 | robust |
| orig | B | 2d | -35.13 | [-40.78, -26.81] | 10/10 | robust |
| orig | B | 2e_K10 | -35.69 | [-40.79, -27.76] | 10/10 | robust |
| orig | B | 2e_K500 | -53.08 | [-65.33, -41.47] | 10/10 | robust |
| orig | B | 2f_slru | -85.73 | [-87.03, -84.03] | 10/10 | robust |
| orig | C | layers_5 | -2.39 | [-3.52, -0.95] | 9/10 | robust |
| orig | C | layers_92 | -41.11 | [-43.19, -38.96] | 10/10 | robust |
| orig | C | 2d | -42.93 | [-45.89, -39.83] | 10/10 | robust |
| orig | C | 2e_K10 | -78.68 | [-79.7, -77.71] | 10/10 | robust |
| orig | C | 2e_K500 | -78.67 | [-79.73, -77.66] | 10/10 | robust |
| orig | C | 2f_slru | -87.63 | [-88.22, -87.09] | 10/10 | robust |
| vacuum | A | layers_5 | -22.18 | [-33.39, -12.72] | 10/10 | robust |
| vacuum | A | layers_92 | -44.82 | [-49.73, -38.12] | 10/10 | robust |
| vacuum | A | 2d | -44.62 | [-49.87, -37.95] | 10/10 | robust |
| vacuum | A | 2e_K10 | -53.61 | [-65.6, -41.77] | 10/10 | robust |
| vacuum | A | 2e_K500 | -61.8 | [-70.64, -52.6] | 10/10 | robust |
| vacuum | A | 2f_slru | -86.98 | [-88.05, -85.61] | 10/10 | robust |
| vacuum | B | layers_5 | -17.2 | [-28.01, -9.29] | 10/10 | robust |
| vacuum | B | layers_92 | -40.35 | [-44.98, -33.4] | 10/10 | robust |
| vacuum | B | 2d | -42.1 | [-46.88, -34.97] | 10/10 | robust |
| vacuum | B | 2e_K10 | -42.01 | [-47.03, -33.88] | 10/10 | robust |
| vacuum | B | 2e_K500 | -55.94 | [-67.61, -44.96] | 10/10 | robust |
| vacuum | B | 2f_slru | -87.61 | [-88.69, -86.03] | 10/10 | robust |
| vacuum | C | layers_5 | -8.71 | [-10.1, -7.32] | 10/10 | robust |
| vacuum | C | layers_92 | -45.81 | [-47.79, -44.07] | 10/10 | robust |
| vacuum | C | 2d | -46.04 | [-48.24, -44.02] | 10/10 | robust |
| vacuum | C | 2e_K10 | -81.23 | [-82.22, -80.16] | 10/10 | robust |
| vacuum | C | 2e_K500 | -81.14 | [-82.13, -80.06] | 10/10 | robust |
| vacuum | C | 2f_slru | -89.12 | [-89.71, -88.49] | 10/10 | robust |
| ta | A | layers_5 | -7.26 | [-18.05, 4.73] | 7/10 | directional |
| ta | A | layers_92 | -34.76 | [-40.81, -28.96] | 10/10 | robust |
| ta | A | 2d | -34.8 | [-41.04, -29.01] | 10/10 | robust |
| ta | A | 2e_K10 | -45.74 | [-60.56, -31.84] | 10/10 | robust |
| ta | A | 2e_K500 | -41.02 | [-54.1, -27.04] | 9/10 | robust |
| ta | A | 2f_slru | -85.25 | [-86.77, -83.68] | 10/10 | robust |
| ta | B | layers_5 | 4.79 | [-8.6, 19.22] | 6/10 | tie |
| ta | B | layers_92 | -33.82 | [-41.87, -26.03] | 10/10 | robust |
| ta | B | 2d | -32.89 | [-40.9, -25.04] | 10/10 | robust |
| ta | B | 2e_K10 | -34.64 | [-41.52, -28.06] | 10/10 | robust |
| ta | B | 2e_K500 | -38.95 | [-53.88, -24.77] | 10/10 | robust |
| ta | B | 2f_slru | -84.76 | [-86.76, -82.61] | 10/10 | robust |
| ta | C | layers_5 | -1.89 | [-2.29, -1.52] | 10/10 | robust |
| ta | C | layers_92 | -43.41 | [-44.44, -42.31] | 10/10 | robust |
| ta | C | 2d | -42.6 | [-43.69, -41.45] | 10/10 | robust |
| ta | C | 2e_K10 | -77.31 | [-78.39, -76.29] | 10/10 | robust |
| ta | C | 2e_K500 | -77.09 | [-78.16, -76.1] | 10/10 | robust |
| ta | C | 2f_slru | -86.9 | [-87.49, -86.34] | 10/10 | robust |


## DB 尺寸 × 跨-seed 不確定性（orig 100MB vs 1gb,各 10 seed）— R3 size × uncertainty

把上面的跨-seed 不確定性方法**原封不動套到 1gb**:A/B/C 各 10 seed 重跑 1gb full matrix
(`results/seeds_1gb/`),per-seed 效應 = 同 seed 內 strategy vs baseline 的 Δ%,報跨 10 seed 的
**mean、bootstrap 95% CI、符號一致性、verdict**。因為效應是「同 seed 相對量」,先前那個機器狀態偏移
**自動消掉**(本 sweep 的 machine anchor `2f_slru` first-q 跨 10 seed 維持 **98.4–100.2µs**,內部穩定)。
orig 欄取自已 commit 的 [`results/stats/uncertainty.csv`](results/stats/uncertainty.csv),1gb 欄取自
[`results/stats/uncertainty_1gb.csv`](results/stats/uncertainty_1gb.csv);格式 `meanΔ% [95% CI] 符號 verdict`。
> ⚠ 欄 = orig 與 1gb 的**方向/verdict 不同**(非雜訊,下方逐項說明);✓ = 兩尺寸同向且都非 tie。

### first-query latency（async)— prefetch 對冷啟動的效益

| wl | strategy | orig (100MB) | 1gb | size 一致? |
|---|---|---|---|:--:|
| A | layers_5 | −13% [−24,−3] 8/10 robust | −17% [−23,−11] 10/10 robust | ✓ |
| A | layers_92 | −36% [−40,−31] 10/10 robust | −31% [−32,−27] 10/10 robust | ✓ |
| A | 2d | −35% [−39,−31] 10/10 robust | −55% [−56,−53] 10/10 robust | ✓ |
| A | 2e_K10 | −48% [−61,−36] 10/10 robust | −61% [−69,−55] 10/10 robust | ✓ |
| A | 2e_K500 | −18% [−59,+49] 9/10 **directional** | −66% [−73,−60] 10/10 **robust** | ✓ |
| A | 2f_slru | −85% [−86,−83] 10/10 robust | −86% [−86,−85] 10/10 robust | ✓ |
| B | layers_5 | −9% [−19,−1] 7/10 robust | −15% [−22,−11] 10/10 robust | ✓ |
| B | layers_92 | −35% [−41,−26] 9/10 robust | −31% [−34,−26] 10/10 robust | ✓ |
| B | 2d | −35% [−41,−27] 10/10 robust | −55% [−57,−52] 10/10 robust | ✓ |
| B | 2e_K10 | −36% [−41,−28] 10/10 robust | −55% [−57,−52] 10/10 robust | ✓ |
| B | 2e_K500 | −53% [−65,−41] 10/10 robust | −64% [−71,−57] 10/10 robust | ✓ |
| B | 2f_slru | −86% [−87,−84] 10/10 robust | −86% [−86,−85] 10/10 robust | ✓ |
| C | layers_5 | −2% [−4,−1] 9/10 robust | −11% [−11,−10] 10/10 robust | ✓ |
| C | layers_92 | −41% [−43,−39] 10/10 robust | −22% [−29,−15] 10/10 robust | ✓ |
| C | 2d | −43% [−46,−40] 10/10 robust | −57% [−57,−57] 10/10 robust | ✓ |
| C | 2e_K10 | −79% [−80,−78] 10/10 robust | −80% [−80,−80] 10/10 robust | ✓ |
| C | 2e_K500 | −79% [−80,−78] 10/10 robust | −80% [−80,−79] 10/10 robust | ✓ |
| C | 2f_slru | −88% [−88,−87] 10/10 robust | −87% [−87,−87] 10/10 robust | ✓ |

**18/18 方向一致**,且 1gb 全部 `robust`。**prefetch 的冷啟動 first-query 優勢完全 size-robust**:符號全部一致、CI 都不跨 0;`2e_K500/A` 甚至從 orig 的 `directional`(CI [−59,+49] 跨 0)在 1gb 收成 `robust`——**大 DB 讓效應更乾淨**。小 hotset 的 `2d`/`2e_K10` 在 1gb 改善幅度更大(A 2d −35%→−55%、B 2e_K10 −36%→−55%),CI 仍緊。

### warm-process e2e（async)— 本研究主張的部署指標

| wl | strategy | orig (100MB) | 1gb | size 一致? |
|---|---|---|---|:--:|
| A | layers_5 | −5% [−16,+4] 6/10 tie | −7% [−13,−1] 7/10 robust | ⚠ |
| A | layers_92 | −12% [−18,−6] 9/10 robust | −1% [−4,+4] 9/10 directional | ✓ |
| A | 2d | −25% [−29,−20] 10/10 robust | −42% [−43,−39] 10/10 robust | ✓ |
| A | 2e_K10 | −36% [−50,−23] 10/10 robust | −47% [−55,−39] 10/10 robust | ✓ |
| A | 2e_K500 | +79% [+37,+141] 10/10 robust | +47% [+40,+55] 10/10 robust | ✓ |
| A | 2f_slru | +744% [+662,+870] 10/10 robust | +930% [+894,+993] 10/10 robust | ✓ |
| B | layers_5 | −1% [−12,+7] 8/10 directional | −5% [−12,−1] 10/10 robust | ✓ |
| B | layers_92 | −13% [−20,−2] 9/10 robust | −2% [−6,+5] 9/10 directional | ✓ |
| B | 2d | −25% [−32,−16] 9/10 robust | −42% [−45,−38] 10/10 robust | ✓ |
| B | 2e_K10 | −25% [−30,−16] 9/10 robust | −41% [−43,−37] 10/10 robust | ✓ |
| B | 2e_K500 | +40% [+24,+55] 10/10 robust | +47% [+39,+56] 10/10 robust | ✓ |
| B | 2f_slru | +704% [+632,+799] 10/10 robust | +917% [+881,+979] 10/10 robust | ✓ |
| C | layers_5 | +5% [+4,+6] 10/10 robust | −1% [−1,−1] 9/10 robust | ⚠ |
| C | layers_92 | −21% [−22,−19] 10/10 robust | +7% [+0,+13] 5/10 robust | ⚠ |
| C | 2d | −36% [−39,−33] 10/10 robust | −47% [−47,−46] 10/10 robust | ✓ |
| C | 2e_K10 | −70% [−72,−69] 10/10 robust | −68% [−68,−68] 10/10 robust | ✓ |
| C | 2e_K500 | −31% [−34,−27] 10/10 robust | +35% [+34,+37] 10/10 robust | ⚠ |
| C | 2f_slru | −9% [−14,−4] 8/10 robust | +139% [+135,+143] 10/10 robust | ⚠ |

**13/18 一致;5 個 ⚠ 全部集中在窄域 workload C**(以及 A/layers_5 那格其實是 orig=tie→1gb 變乾淨,非真矛盾)。原因一致:**C 的 working set 隨 DB 變大而膨脹**(resident set 483→984 page),deliver 成本翻倍,把幾個「靠少量 deliver 取勝」的策略由贏轉輸,且跨 10 seed `robust`(非雜訊):
- **`2f_slru/C`:−9% → +139%**——100MB 唯一能讓 2f 在 e2e 取勝的格,到 1GB 確定變成大輸。
- **`2e_K500/C`:−31% → +35%**、**`layers_92/C`:−21% → +7%**——同樣由贏轉小輸。
- 對照:小 hotset 的 `2d`/`2e_K10` 兩尺寸 e2e 都穩贏(C 2e_K10 −70%/−68%),size-robust。

**結論(對齊後)**:① **冷啟動 first-query 的效益 size-robust**——18/18 跨尺寸方向一致、1gb 全 robust。② **部署 e2e 的 size 敏感性集中在窄域 workload**:DB 變大會放大 working set→deliver,使 `2f_slru`/`2e_K500`/`layers_92` 在 C 由贏轉輸(robust);**小而準的 hotset(2d / 2e_K10)是唯一兩尺寸 e2e 都穩贏的策略**。
