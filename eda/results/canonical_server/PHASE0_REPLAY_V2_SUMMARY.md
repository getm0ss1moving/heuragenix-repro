# checkpoint replay v2 summary (paired vs same-checkpoint control)

| design | stage | action | n | gate_ok | d_setupWNS | d_holdWNS | d_TNS | d_HPWL(um) | d_WL(um) | d_vias | d_power(W) | U | dur(s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aes | post_cts | grt200 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 896.1 |
| aes | post_cts | grt50 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 909.4 |
| aes | post_cts | layeradj_std | 5 | 0 | 0.09972 | -0.03612 | 14.96 | 0 | -6849 | -4809 | -0.00048 | 0.02361 | 564.2 |
| aes | post_cts | slew0 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 884.5 |
| aes | post_global_place | grt200 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 960.9 |
| aes | post_global_place | grt50 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 998.2 |
| aes | post_global_place | layeradj_std | 5 | 2 | 0.04652 | -0.022 | 12.91 | 0 | -5496 | -4516 | -0.00028 | 0.01999 | 650.7 |
| aes | post_global_place | slew0 | 5 | 1 | -0.1682 | -0.004409 | -43.01 | -9854 | 3433 | -123.6 | -0.00012 | -0.06332 | 1002 |
| gcd | post_cts | grt200 | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 22.86 |
| gcd | post_cts | grt50 | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 23.18 |
| gcd | post_cts | layeradj_std | 11 | 11 | -0.006926 | 0.003433 | 0.5474 | 0 | -50.18 | -8.545 | -1.273e-06 | 0.01294 | 21.68 |
| gcd | post_global_place | grt200 | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 23.97 |
| gcd | post_global_place | grt50 | 11 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 23.39 |
| gcd | post_global_place | layeradj_std | 11 | 11 | 0.00312 | 0.003374 | 0.5637 | 0 | -28.82 | -2 | -1.818e-07 | 0.01387 | 22.53 |
| ibex | post_cts | cap0 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 595.3 |
| ibex | post_cts | grt200 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 606.8 |
| ibex | post_cts | grt50 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 634.9 |
| ibex | post_cts | layeradj_std | 3 | 1 | 0.1189 | -0.05037 | 27.01 | 0 | -5658 | -2941 | -0.0002667 | 0.04087 | 455.2 |
| ibex | post_cts | slew0 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 590.6 |
| ibex | post_global_place | cap0 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 700.5 |
| ibex | post_global_place | grt200 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 717.7 |
| ibex | post_global_place | grt50 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 713.7 |
| ibex | post_global_place | layeradj_std | 3 | 0 | 0.1312 | -0.04868 | 29.76 | 0 | -4733 | -2692 | -0.0002 | 0.04074 | 532.6 |
| ibex | post_global_place | slew0 | 3 | 1 | 0.1246 | 0.001625 | -9.817 | 1954 | 4214 | 337 | -6.667e-05 | -0.02238 | 743.2 |
| jpeg | post_cts | cap0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1056 |
| jpeg | post_cts | grt200 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 997.2 |
| jpeg | post_cts | grt50 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 908.5 |
| jpeg | post_cts | layeradj_std | 4 | 4 | 0.08499 | 0.0136 | 9.177 | 0 | -2787 | -396 | -0.001 | 0.0353 | 862.6 |
| jpeg | post_cts | slew0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1020 |
| jpeg | post_global_place | cap0 | 4 | 4 | -0.0007563 | -0.002956 | -1.999 | 0.1812 | -193.5 | -117.5 | 0 | -0.006967 | 968.4 |
| jpeg | post_global_place | grt200 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 990.1 |
| jpeg | post_global_place | grt50 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1036 |
| jpeg | post_global_place | layeradj_std | 4 | 4 | 0.06329 | 0.01118 | 6.138 | 0 | -3198 | -548.5 | -0.001 | 0.02309 | 1017 |
| jpeg | post_global_place | slew0 | 4 | 4 | 0.004182 | -0.001043 | -1.339 | -6.705 | -62 | -111.2 | 0 | -0.005274 | 986 |

Oracle (per-decision, gate-safe, canonical U) counts:
- aes/post_cts/grt200: 5
- aes/post_global_place/grt200: 3
- aes/post_global_place/layeradj_std: 2
- gcd/post_cts/grt200: 3
- gcd/post_cts/layeradj_std: 8
- gcd/post_global_place/grt200: 1
- gcd/post_global_place/layeradj_std: 10
- ibex/post_cts/cap0: 2
- ibex/post_cts/layeradj_std: 1
- ibex/post_global_place/cap0: 3
- jpeg/post_cts/layeradj_std: 4
- jpeg/post_global_place/layeradj_std: 4
