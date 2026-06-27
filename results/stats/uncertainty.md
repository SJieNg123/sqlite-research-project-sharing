# R3 workload-sensitivity uncertainty

Pooled seeds: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 (n=10). Bootstrap 95% CI of the mean per-seed effect; effect = strategy vs same-seed baseline.

### e2e_warm_us — async arm, layout orig

| workload | strategy | mean Δ% | 95% CI | sign | verdict |
|---|---|---:|---|---:|---|
| A | layers_5 | -5.1 | [-15.9, +4.4] | 6/10 | tie |
| A | layers_92 | -12.5 | [-18.1, -5.7] | 9/10 | robust |
| A | 2d | -24.9 | [-29.4, -19.8] | 10/10 | robust |
| A | 2e_K10 | -36.0 | [-50.0, -23.1] | 10/10 | robust |
| A | 2e_K500 | +79.1 | [+36.5, +141.4] | 10/10 | robust |
| A | 2f_slru | +744.1 | [+661.7, +870.2] | 10/10 | robust |
| B | layers_5 | -1.3 | [-11.7, +6.7] | 8/10 | directional |
| B | layers_92 | -13.2 | [-20.4, -1.7] | 9/10 | robust |
| B | 2d | -25.4 | [-31.6, -16.2] | 9/10 | robust |
| B | 2e_K10 | -24.6 | [-30.3, -15.6] | 9/10 | robust |
| B | 2e_K500 | +40.2 | [+24.5, +55.1] | 10/10 | robust |
| B | 2f_slru | +703.6 | [+631.9, +799.0] | 10/10 | robust |
| C | layers_5 | +4.8 | [+3.8, +6.1] | 10/10 | robust |
| C | layers_92 | -20.6 | [-22.0, -19.2] | 10/10 | robust |
| C | 2d | -35.9 | [-38.5, -33.1] | 10/10 | robust |
| C | 2e_K10 | -70.5 | [-71.9, -69.1] | 10/10 | robust |
| C | 2e_K500 | -30.6 | [-34.1, -27.3] | 10/10 | robust |
| C | 2f_slru | -9.0 | [-13.9, -4.1] | 8/10 | robust |

### first_query_us — async arm, layout orig

| workload | strategy | mean Δ% | 95% CI | sign | verdict |
|---|---|---:|---|---:|---|
| A | layers_5 | -13.2 | [-24.4, -3.3] | 8/10 | robust |
| A | layers_92 | -35.6 | [-39.6, -31.4] | 10/10 | robust |
| A | 2d | -35.1 | [-38.9, -31.0] | 10/10 | robust |
| A | 2e_K10 | -47.7 | [-60.9, -35.8] | 10/10 | robust |
| A | 2e_K500 | -17.6 | [-59.1, +48.9] | 9/10 | directional |
| A | 2f_slru | -84.9 | [-86.3, -82.6] | 10/10 | robust |
| B | layers_5 | -9.0 | [-19.4, -0.9] | 7/10 | robust |
| B | layers_92 | -34.9 | [-40.9, -25.6] | 9/10 | robust |
| B | 2d | -35.1 | [-40.8, -26.8] | 10/10 | robust |
| B | 2e_K10 | -35.7 | [-40.8, -27.8] | 10/10 | robust |
| B | 2e_K500 | -53.1 | [-65.3, -41.5] | 10/10 | robust |
| B | 2f_slru | -85.7 | [-87.0, -84.0] | 10/10 | robust |
| C | layers_5 | -2.4 | [-3.5, -0.9] | 9/10 | robust |
| C | layers_92 | -41.1 | [-43.2, -39.0] | 10/10 | robust |
| C | 2d | -42.9 | [-45.9, -39.8] | 10/10 | robust |
| C | 2e_K10 | -78.7 | [-79.7, -77.7] | 10/10 | robust |
| C | 2e_K500 | -78.7 | [-79.7, -77.7] | 10/10 | robust |
| C | 2f_slru | -87.6 | [-88.2, -87.1] | 10/10 | robust |

### e2e_us — async arm, layout orig

| workload | strategy | mean Δ% | 95% CI | sign | verdict |
|---|---|---:|---|---:|---|
| A | layers_5 | +18.9 | [+7.8, +28.5] | 7/10 | robust |
| A | layers_92 | +12.0 | [+4.6, +22.1] | 9/10 | robust |
| A | 2d | -0.4 | [-6.6, +7.4] | 6/10 | tie |
| A | 2e_K10 | -12.3 | [-27.5, +2.6] | 8/10 | directional |
| A | 2e_K500 | +103.2 | [+59.4, +165.9] | 10/10 | robust |
| A | 2f_slru | +769.1 | [+684.2, +899.2] | 10/10 | robust |
| B | layers_5 | +21.7 | [+11.6, +29.8] | 8/10 | robust |
| B | layers_92 | +9.7 | [+0.9, +23.1] | 8/10 | robust |
| B | 2d | -2.4 | [-10.1, +8.7] | 8/10 | directional |
| B | 2e_K10 | -1.8 | [-8.8, +8.7] | 8/10 | directional |
| B | 2e_K500 | +63.0 | [+46.0, +79.6] | 10/10 | robust |
| B | 2f_slru | +727.1 | [+653.7, +824.4] | 10/10 | robust |
| C | layers_5 | +26.4 | [+24.6, +28.1] | 10/10 | robust |
| C | layers_92 | +1.0 | [-0.6, +2.6] | 6/10 | tie |
| C | 2d | -14.3 | [-16.6, -11.9] | 10/10 | robust |
| C | 2e_K10 | -49.0 | [-51.6, -46.6] | 10/10 | robust |
| C | 2e_K500 | -9.1 | [-13.6, -4.8] | 9/10 | robust |
| C | 2f_slru | +12.6 | [+6.7, +18.5] | 9/10 | robust |

