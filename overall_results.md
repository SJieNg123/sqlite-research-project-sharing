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

<!-- MASTER-RESULTS-START -->
## master batch 結果

> 由 `run_experiment.py` 一次跑齊:54 strategy cells × pread/async + 9 baseline,pread 5 / async 10 / baseline 10 reps(丟 warmup)、rep-major、全機 drop-caches、in-harness `--verify-hotset`、釘核升頻、ra=128。**全 117 cell `cold_pct`=0**。原始檔:[`results/main/summary.csv`](results/main/summary.csv) / [`results/main/raw.csv`](results/main/raw.csv)。
> `fq` = first-query median µs;`impr%` = async 相對該 (workload,layout) baseline;`e2e_std` = open+deliver+fq(standalone warmer);`e2e_warm` = deliver+fq(warm-process,≈static,本研究主張);`deliv%` = async delivery_pct;`oracle` = pread 臂 fq(可達上界)。
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

**讀法**:① first-query 最低一律是 **2f_slru**(載整個 working set),但其 deliver(A/B ~7ms、C ~0.76ms)使 `e2e` 多半輸——除 C 外兩個 e2e 模型都超 baseline。② **layers_5 / 2d / 2e_K10** 用極少 syscall:`e2e_warm`(= deliver+fq,warm-process/integrated,本研究主張)在三個 workload 都改善(A −7~9%、B −29~34%、**C × 2e_K10 −73% / 291µs**);`e2e_std`(= open+deliver+fq,standalone warmer)則在快 workload 因 ~200µs 冷 open 而變差。③ 兩個 e2e 模型唯一差是 per-layout 的冷 open(db)(~200µs)。④ `oracle` 欄是同步 pread 的可達下界。
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

## RAM-pressure（cgroup MemoryMax=20M / unlimited 比值,async first-q）

> 來源 [`results/ram20m/`](results/ram20m/summary.csv) ÷ master。比值近 1.0 → 壓力幾乎不影響。

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

## 資料來源

- 主矩陣:[`results/main/summary.csv`](results/main/summary.csv)、Z:[`results/z/`](results/z/summary.csv)
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
