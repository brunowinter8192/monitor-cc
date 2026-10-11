# PDF conversion QA - M1 measurements

## Scope

34 windows, 235 pages. Result rows per candidate: C1 42, C2 12, C3 42, C4a 102, C4b 102, C5a 102, C5b 102. Whole-document rows: 84.

## Startup floor (1-page PDF, 3 runs)

| candidate | runs | wall_s each | median_s |
|---|---|---|---|
| C1 | 3 | [14.47, 14.23, 14.62] | 14.47 |
| C2 | 3 | [14.23, 14.08, 14.28] | 14.23 |
| C3 | 3 | [12.36, 11.67, 13.18] | 12.36 |
| C4a | 3 | [0.41, 0.4, 0.4] | 0.4 |
| C4b | 3 | [0.4, 0.45, 0.46] | 0.45 |
| C5a | 3 | [0.08, 0.08, 0.08] | 0.08 |
| C5b | 3 | [0.69, 0.68, 0.72] | 0.69 |

## Results per candidate (one run per window, rep 1, ok windows for speed)

| candidate | ok | success | s/page pooled | s/page minus startup | s/page median window | peak GB median | peak GB max | min available GB |
|---|---|---|---|---|---|---|---|---|
| C1 | 34/34 | 100% | 13.049 | 10.956 | 12.217 | 4.98 | 5.56 | 17.43 |
| C2 | 4/4 | 100% | 14.064 | 11.477 | 13.619 | 4.74 | 5.22 | 17.64 |
| C3 | 34/34 | 100% | 3.208 | 1.421 | 2.662 | 4.23 | 18.01 | 15.38 |
| C4a | 34/34 | 100% | 0.235 | 0.177 | 0.144 | 0.16 | 0.44 | 21.76 |
| C4b | 34/34 | 100% | 0.392 | 0.327 | 0.157 | 0.4 | 0.69 | 21.45 |
| C5a | 34/34 | 100% | 0.014 | 0.002 | 0.013 | 0.01 | 0.01 | 22.41 |
| C5b | 34/34 | 100% | 0.112 | 0.044 | 0.087 | 0.1 | 0.91 | 21.79 |

## Failures by reason (all reps)

none

### Failed rows

none

## Character recall vs pdftotext layer, text windows

Pooled (sum matched / sum reference) over ok windows of each candidate.

| candidate | windows | recall | recall special | recall umlaut | out/ref length | ref special chars | ref umlauts |
|---|---|---|---|---|---|---|---|
| C1 | 31 | 0.9243 | 0.4293 | 0.8528 | 0.9693 | 941 | 2805 |
| C2 | 3 | 0.9611 | 0.2609 | 0.8738 | 1.0972 | 46 | 206 |
| C3 | 31 | 0.9235 | 0.8523 | 0.9362 | 0.9754 | 941 | 2805 |
| C4a | 31 | 0.8787 | 0.9129 | 0.8731 | 0.9295 | 941 | 2805 |
| C4b | 31 | 0.9424 | 0.9862 | 0.9989 | 0.976 | 941 | 2805 |
| C5a | 31 | 0.971 | 0.0967 | 0.985 | 1.0001 | 941 | 2805 |
| C5b | 31 | 0.9716 | 0.0978 | 0.985 | 1.0012 | 941 | 2805 |

Same, restricted to the 31 windows measured by every candidate except C2 (C2 ran only on the panel).

| candidate | windows | recall | recall special | recall umlaut | out/ref length | ref special chars | ref umlauts |
|---|---|---|---|---|---|---|---|
| C1 | 31 | 0.9243 | 0.4293 | 0.8528 | 0.9693 | 941 | 2805 |
| C3 | 31 | 0.9235 | 0.8523 | 0.9362 | 0.9754 | 941 | 2805 |
| C4a | 31 | 0.8787 | 0.9129 | 0.8731 | 0.9295 | 941 | 2805 |
| C4b | 31 | 0.9424 | 0.9862 | 0.9989 | 0.976 | 941 | 2805 |
| C5a | 31 | 0.971 | 0.0967 | 0.985 | 1.0001 | 941 | 2805 |
| C5b | 31 | 0.9716 | 0.0978 | 0.985 | 1.0012 | 941 | 2805 |

## Character recall vs pdftotext layer, formula windows (indicative only)

Pooled (sum matched / sum reference) over ok windows of each candidate.

| candidate | windows | recall | recall special | recall umlaut | out/ref length | ref special chars | ref umlauts |
|---|---|---|---|---|---|---|---|
| C1 | 3 | 0.9487 | 0.1818 |  | 1.3534 | 44 | 0 |
| C2 | 1 | 0.9202 | 0.0 |  | 1.7815 | 10 | 0 |
| C3 | 3 | 0.8955 | 1.0 |  | 1.0866 | 44 | 0 |
| C4a | 3 | 0.556 | 1.0 |  | 0.9707 | 44 | 0 |
| C4b | 3 | 0.5082 | 1.0 |  | 0.6272 | 44 | 0 |
| C5a | 3 | 0.974 | 0.0 |  | 1.0143 | 44 | 0 |
| C5b | 3 | 0.9748 | 0.0 |  | 1.0164 | 44 | 0 |

Same, restricted to the 3 windows measured by every candidate except C2 (C2 ran only on the panel).

| candidate | windows | recall | recall special | recall umlaut | out/ref length | ref special chars | ref umlauts |
|---|---|---|---|---|---|---|---|
| C1 | 3 | 0.9487 | 0.1818 |  | 1.3534 | 44 | 0 |
| C3 | 3 | 0.8955 | 1.0 |  | 1.0866 | 44 | 0 |
| C4a | 3 | 0.556 | 1.0 |  | 0.9707 | 44 | 0 |
| C4b | 3 | 0.5082 | 1.0 |  | 0.6272 | 44 | 0 |
| C5a | 3 | 0.974 | 0.0 |  | 1.0143 | 44 | 0 |
| C5b | 3 | 0.9748 | 0.0 |  | 1.0164 | 44 | 0 |

## Status ok but recall below 0.5 (silent content loss, rep 1, includes formula windows)

| candidate | windows | which |
|---|---|---|
| C1 | 1 | CoenenbergKostenrechnungKost 0.45 |
| C2 | 0 |  |
| C3 | 1 | CoenenbergKostenrechnungKost 0.46 |
| C4a | 4 | BoatrightBusinessEthicsMista 0.11; GrundeiZaumseilAufsichtsratC 0.02; GrundeiZaumseilAufsichtsratC 0.02; EfronMorris1975SteinEstimato 0.08 |
| C4b | 2 | BoatrightBusinessEthicsMista 0.09; EfronMorris1975SteinEstimato 0.06 |
| C5a | 0 |  |
| C5b | 0 |  |

## Cleanup class counts (SKILL regexes, totals over ok windows, rep 1)

| candidate | pages | A | B | C | F | G | H | I | A: U+FFFD | J (lines+blocks >1000) | I >2000 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 235 | 0 | 975 | 17 | 48 | 65 | 0 | 2 | 0 | 219 | 0 |
| C2 | 22 | 0 | 627 | 0 | 5 | 2 | 0 | 0 | 0 | 4 | 0 |
| C3 | 235 | 3 | 1 | 17 | 46 | 152 | 0 | 0 | 3 | 240 | 0 |
| C4a | 235 | 425 | 21 | 0 | 0 | 0 | 95 | 15 | 425 | 97 | 0 |
| C4b | 235 | 167 | 19 | 0 | 0 | 0 | 48 | 5 | 167 | 185 | 0 |
| C5a | 235 | 3 | 18 | 0 | 0 | 30 | 241 | 7 | 3 | 256 | 0 |
| C5b | 235 | 3 | 18 | 0 | 0 | 30 | 240 | 7 | 3 | 257 | 0 |

## Highest process-tree peaks of the MinerU candidates

| candidate | window | pages | peak GB | min available GB | wall_s |
|---|---|---|---|---|---|
| C1 | EfronMorris1975SteinEstimatorDataA_p0001 | 10 | 5.557 | 22.032 | 313.17 |
| C1 | KeKellyXiu2019PredictingReturnsTex_p0040 | 9 | 5.469 | 21.47 | 157.75 |
| C1 | KeKellyXiu2019PredictingReturnsTex_p0040 | 9 | 5.437 | 22.499 | 154.34 |
| C2 | KeKellyXiu2019PredictingReturnsTex_p0040 | 9 | 5.475 | 10.162 | 156.87 |
| C2 | WelgeEulerichCorporateGovernanceMa_p0021 | 6 | 5.221 | 10.391 | 60.56 |
| C2 | CoenenbergKostenrechnungKostenanal_p0496 | 6 | 5.22 | 21.546 | 78.05 |
| C3 | EfronMorris1975SteinEstimatorDataA_p0001 | 10 | 18.009 | 15.379 | 59.98 |
| C3 | CollinsBusinessEthicsOxymoron_p0001-0008 | 8 | 16.009 | 17.83 | 72.93 |
| C3 | BoatrightBusinessEthicsMistake_p0001-001 | 10 | 12.009 | 18.058 | 39.63 |

## Pooled wall seconds per page by window group (ok windows)

| candidate | book_early | book_mid | ewert_crash_dense_chars | ewert_crash_item_fraction | formula | medium | short |
|---|---|---|---|---|---|---|---|
| C1 | 10.889 | 12.391 | 11.344 | 10.8 | 20.5 | 11.5 | 13.864 |
| C2 | 9.988 | 13.008 |  |  | 17.467 |  | 14.23 |
| C3 | 2.806 | 3.049 | 2.047 | 2.1 | 3.442 | 2.771 | 4.381 |
| C4a | 0.265 | 0.31 | 0.111 | 0.117 | 0.353 | 0.12 | 0.196 |
| C4b | 0.188 | 0.193 | 0.113 | 0.135 | 1.413 | 0.216 | 0.478 |
| C5a | 0.016 | 0.017 | 0.01 | 0.01 | 0.011 | 0.009 | 0.015 |
| C5b | 0.139 | 0.103 | 0.01 | 0.111 | 0.083 | 0.103 | 0.132 |

## Stability panel (MinerU candidates, repeated windows)

| candidate | window | runs | status | wall_s | peak GB | distinct md hashes |
|---|---|---|---|---|---|---|
| C1 | CoenenbergKostenrechnungKostenanal_p0496-0501 | 3 | ok/ok/ok | 78.63/77.61/77.11 | 4.817/5.219/5.179 | 1 |
| C1 | KeKellyXiu2019PredictingReturnsTex_p0040-0048 | 3 | ok/ok/ok | 154.34/155.0/157.75 | 5.437/5.032/5.469 | 1 |
| C1 | WelgeEulerichCorporateGovernanceMa_p0021-0026 | 3 | ok/ok/ok | 58.85/59.02/59.05 | 5.181/5.179/5.184 | 1 |
| C2 | CoenenbergKostenrechnungKostenanal_p0496-0501 | 3 | ok/ok/ok | 78.05/84.93/78.52 | 5.22/4.906/4.825 | 1 |
| C2 | KeKellyXiu2019PredictingReturnsTex_p0040-0048 | 3 | ok/ok/ok | 157.2/156.87/445.53 | 4.858/5.475/4.593 | 1 |
| C2 | WelgeEulerichCorporateGovernanceMa_p0021-0026 | 3 | ok/ok/ok | 59.93/60.56/60.04 | 4.624/5.221/4.782 | 1 |
| C3 | CoenenbergKostenrechnungKostenanal_p0496-0501 | 3 | ok/ok/ok | 18.67/17.73/17.6 | 4.209/4.292/4.313 | 1 |
| C3 | KeKellyXiu2019PredictingReturnsTex_p0040-0048 | 3 | ok/ok/ok | 15.75/15.84/15.35 | 3.92/3.865/3.946 | 1 |
| C3 | WelgeEulerichCorporateGovernanceMa_p0021-0026 | 3 | ok/ok/ok | 13.53/13.44/13.44 | 3.621/3.655/3.65 | 1 |

### C1 vs C2 output hash

| window | rep | C1 | C2 | C1 sha | C2 sha | md |
|---|---|---|---|---|---|---|
| CoenenbergKostenrechnungKostenanal_p0496-0501 | 1 | ok | ok | 0f234cd423fbdce4 | 0f234cd423fbdce4 | identical |
| CoenenbergKostenrechnungKostenanal_p0496-0501 | 2 | ok | ok | 0f234cd423fbdce4 | 0f234cd423fbdce4 | identical |
| CoenenbergKostenrechnungKostenanal_p0496-0501 | 3 | ok | ok | 0f234cd423fbdce4 | 0f234cd423fbdce4 | identical |
| KeKellyXiu2019PredictingReturnsTex_p0040-0048 | 1 | ok | ok | 36ca74b1a3b9dbe4 | 36ca74b1a3b9dbe4 | identical |
| KeKellyXiu2019PredictingReturnsTex_p0040-0048 | 2 | ok | ok | 36ca74b1a3b9dbe4 | 36ca74b1a3b9dbe4 | identical |
| KeKellyXiu2019PredictingReturnsTex_p0040-0048 | 3 | ok | ok | 36ca74b1a3b9dbe4 | 36ca74b1a3b9dbe4 | identical |
| TelekomPibMagentaZuhauseL_p0001-0001 | 1 | ok | ok | 710428b540687008 | 710428b540687008 | identical |
| TelekomPibMagentaZuhauseL_p0001-0001 | 2 | ok | ok | 710428b540687008 | 710428b540687008 | identical |
| TelekomPibMagentaZuhauseL_p0001-0001 | 3 | ok | ok | 710428b540687008 | 710428b540687008 | identical |
| WelgeEulerichCorporateGovernanceMa_p0021-0026 | 1 | ok | ok | 7ba6f78eb7202472 | 7ba6f78eb7202472 | identical |
| WelgeEulerichCorporateGovernanceMa_p0021-0026 | 2 | ok | ok | 7ba6f78eb7202472 | 7ba6f78eb7202472 | identical |
| WelgeEulerichCorporateGovernanceMa_p0021-0026 | 3 | ok | ok | 7ba6f78eb7202472 | 7ba6f78eb7202472 | identical |

## Timing of cheap candidates, n=3 (pooled s/page per full pass)

| candidate | pass 1 / 2 / 3 | median | max/min |
|---|---|---|---|
| C4a | 0.2346 / 0.2394 / 0.2420 | 0.2394 | 1.032 |
| C4b | 0.3920 / 0.3957 / 0.4071 | 0.3957 | 1.039 |
| C5a | 0.0140 / 0.0136 / 0.0142 | 0.014 | 1.041 |
| C5b | 0.1121 / 0.1132 / 0.1209 | 0.1132 | 1.078 |

## Whole documents (21 wise2627 PDFs, one run per candidate)

| candidate | ok | pages | wall_s | pages/s | peak GB max | min available GB | recall (5 sampled pages/doc) |
|---|---|---|---|---|---|---|---|
| C4a | 21/21 | 5130 | 1718.8 | 2.98 | 0.53 | 25.89 | 0.8835 |
| C4b | 21/21 | 5130 | 832.6 | 6.16 | 0.95 | 25.17 | 0.9492 |
| C5a | 21/21 | 5130 | 35.6 | 144.3 | 1.19 | 25.97 | 0.9691 |
| C5b | 21/21 | 5130 | 367.3 | 13.97 | 1.9 | 25.39 | 0.9697 |

### Per document

| document | pages | candidate | status | wall_s | pages/s | peak GB | pages_out | recall | failure |
|---|---|---|---|---|---|---|---|---|---|
| BasnerMcGuireNoiseAndSleepReview20 | 45 | C4a | ok | 5.64 | 7.979 | 0.303 | 45 | 0.8267 |  |
| BasnerMcGuireNoiseAndSleepReview20 | 45 | C4b | ok | 12.2 | 3.689 | 0.604 | 45 | 0.866 |  |
| BasnerMcGuireNoiseAndSleepReview20 | 45 | C5a | ok | 0.25 | 180.0 | 0.008 | 45 | 0.9495 |  |
| BasnerMcGuireNoiseAndSleepReview20 | 45 | C5b | ok | 2.18 | 20.642 | 0.463 | 45 | 0.9532 |  |
| BoatrightBusinessEthicsMistake_199 | 10 | C4a | ok | 2.07 | 4.831 | 0.307 | 10 | 0.1709 |  |
| BoatrightBusinessEthicsMistake_199 | 10 | C4b | ok | 14.74 | 0.678 | 0.689 | 10 | 0.1445 |  |
| BoatrightBusinessEthicsMistake_199 | 10 | C5a | ok | 0.14 | 71.429 | 0.008 | 10 | 0.9494 |  |
| BoatrightBusinessEthicsMistake_199 | 10 | C5b | ok | 0.72 | 13.889 | 0.177 | 10 | 0.9509 |  |
| BoschBadiaCsrFriedmanPorterKramer_ | 5 | C4a | ok | 1.06 | 4.717 | 0.162 | 5 | 1.0 |  |
| BoschBadiaCsrFriedmanPorterKramer_ | 5 | C4b | ok | 0.96 | 5.208 | 0.381 | 5 | 1.0 |  |
| BoschBadiaCsrFriedmanPorterKramer_ | 5 | C5a | ok | 0.08 | 62.5 | 0.008 | 5 | 0.9912 |  |
| BoschBadiaCsrFriedmanPorterKramer_ | 5 | C5b | ok | 0.08 | 62.5 | 0.008 | 5 | 0.9912 |  |
| CoenenbergKostenrechnungKostenanal | 993 | C4a | ok | 77.79 | 12.765 | 0.261 | 993 | 0.9094 |  |
| CoenenbergKostenrechnungKostenanal | 993 | C4b | ok | 75.01 | 13.238 | 0.883 | 993 | 0.999 |  |
| CoenenbergKostenrechnungKostenanal | 993 | C5a | ok | 2.52 | 394.048 | 0.339 | 993 | 0.9922 |  |
| CoenenbergKostenrechnungKostenanal | 993 | C5b | ok | 125.68 | 7.901 | 1.002 | 993 | 0.9923 |  |
| CollinsBusinessEthicsOxymoron_1994 | 8 | C4a | ok | 1.59 | 5.031 | 0.189 | 8 | 1.0 |  |
| CollinsBusinessEthicsOxymoron_1994 | 8 | C4b | ok | 3.32 | 2.41 | 0.592 | 8 | 1.0 |  |
| CollinsBusinessEthicsOxymoron_1994 | 8 | C5a | ok | 0.15 | 53.333 | 0.009 | 8 | 0.9932 |  |
| CollinsBusinessEthicsOxymoron_1994 | 8 | C5b | ok | 0.5 | 16.0 | 0.105 | 8 | 0.9934 |  |
| DeitelIntroPythonDataScience_2020 | 887 | C4a | ok | 51.11 | 17.355 | 0.532 | 887 | 0.6511 |  |
| DeitelIntroPythonDataScience_2020 | 887 | C4b | ok | 102.0 | 8.696 | 0.948 | 887 | 0.9933 |  |
| DeitelIntroPythonDataScience_2020 | 887 | C5a | ok | 2.09 | 424.402 | 0.397 | 887 | 0.8058 |  |
| DeitelIntroPythonDataScience_2020 | 887 | C5b | ok | 29.67 | 29.896 | 0.966 | 887 | 0.8058 |  |
| Din5008Onlinematerialien | 18 | C4a | ok | 1.41 | 12.766 | 0.16 | 18 | 0.9441 |  |
| Din5008Onlinematerialien | 18 | C4b | ok | 1.67 | 10.778 | 0.416 | 18 | 0.9659 |  |
| Din5008Onlinematerialien | 18 | C5a | ok | 0.09 | 200.0 | 0.008 | 18 | 0.8987 |  |
| Din5008Onlinematerialien | 18 | C5b | ok | 3.09 | 5.825 | 0.94 | 18 | 0.8987 |  |
| EntegaAgbCommodity_2026_03 | 6 | C4a | ok | 1.45 | 4.138 | 0.168 | 6 | 0.9999 |  |
| EntegaAgbCommodity_2026_03 | 6 | C4b | ok | 1.38 | 4.348 | 0.388 | 6 | 0.9954 |  |
| EntegaAgbCommodity_2026_03 | 6 | C5a | ok | 0.08 | 75.0 | 0.008 | 6 | 0.9769 |  |
| EntegaAgbCommodity_2026_03 | 6 | C5b | ok | 0.49 | 12.245 | 0.104 | 6 | 0.9769 |  |
| EwertWagenhoferRohlfingBastianInte | 734 | C4a | ok | 51.02 | 14.387 | 0.191 | 734 | 0.9785 |  |
| EwertWagenhoferRohlfingBastianInte | 734 | C4b | ok | 78.55 | 9.344 | 0.854 | 734 | 0.9299 |  |
| EwertWagenhoferRohlfingBastianInte | 734 | C5a | ok | 2.36 | 311.017 | 0.311 | 734 | 0.9802 |  |
| EwertWagenhoferRohlfingBastianInte | 734 | C5b | ok | 71.62 | 10.249 | 0.816 | 734 | 0.9802 |  |
| FriedmanSocialResponsibilityProfit | 6 | C4a | ok | 1.98 | 3.03 | 0.165 | 6 | 1.0 |  |
| FriedmanSocialResponsibilityProfit | 6 | C4b | ok | 2.71 | 2.214 | 0.378 | 6 | 1.0 |  |
| FriedmanSocialResponsibilityProfit | 6 | C5a | ok | 0.22 | 27.273 | 0.012 | 6 | 0.9997 |  |
| FriedmanSocialResponsibilityProfit | 6 | C5b | ok | 0.16 | 37.5 | 0.008 | 6 | 0.9997 |  |
| GrundeiZaumseilAufsichtsratCorpora | 433 | C4a | ok | 1295.21 | 0.334 | 0.477 | 433 | 0.0412 |  |
| GrundeiZaumseilAufsichtsratCorpora | 433 | C4b | ok | 363.24 | 1.192 | 0.812 | 433 | 0.9994 |  |
| GrundeiZaumseilAufsichtsratCorpora | 433 | C5a | ok | 22.37 | 19.356 | 1.194 | 433 | 0.9965 |  |
| GrundeiZaumseilAufsichtsratCorpora | 433 | C5b | ok | 78.26 | 5.533 | 1.898 | 433 | 0.9965 |  |
| KuepperControlling_2024 | 658 | C4a | ok | 136.52 | 4.82 | 0.182 | 658 | 0.9959 |  |
| KuepperControlling_2024 | 658 | C4b | ok | 58.4 | 11.267 | 0.542 | 658 | 0.9995 |  |
| KuepperControlling_2024 | 658 | C5a | ok | 1.64 | 401.22 | 0.262 | 658 | 0.9347 |  |
| KuepperControlling_2024 | 658 | C5b | ok | 6.23 | 105.618 | 0.913 | 658 | 0.9375 |  |
| PiesHielscherBeckmannMoralCommitme | 28 | C4a | ok | 2.25 | 12.444 | 0.161 | 28 | 0.9998 |  |
| PiesHielscherBeckmannMoralCommitme | 28 | C4b | ok | 2.29 | 12.227 | 0.389 | 28 | 0.9998 |  |
| PiesHielscherBeckmannMoralCommitme | 28 | C5a | ok | 0.14 | 200.0 | 0.008 | 28 | 0.9894 |  |
| PiesHielscherBeckmannMoralCommitme | 28 | C5b | ok | 1.49 | 18.792 | 0.444 | 28 | 0.9894 |  |
| PrakashPotoskiVoluntaryEnvironment | 20 | C4a | ok | 1.77 | 11.299 | 0.164 | 20 | 1.0 |  |
| PrakashPotoskiVoluntaryEnvironment | 20 | C4b | ok | 1.93 | 10.363 | 0.395 | 20 | 1.0 |  |
| PrakashPotoskiVoluntaryEnvironment | 20 | C5a | ok | 0.14 | 142.857 | 0.009 | 20 | 0.9829 |  |
| PrakashPotoskiVoluntaryEnvironment | 20 | C5b | ok | 0.14 | 142.857 | 0.008 | 20 | 0.9829 |  |
| ShefrinBehavioralRiskManagement_20 | 520 | C4a | ok | 26.89 | 19.338 | 0.178 | 520 | 1.0 |  |
| ShefrinBehavioralRiskManagement_20 | 520 | C4b | ok | 34.37 | 15.129 | 0.548 | 520 | 1.0 |  |
| ShefrinBehavioralRiskManagement_20 | 520 | C5a | ok | 1.06 | 490.566 | 0.216 | 520 | 0.9871 |  |
| ShefrinBehavioralRiskManagement_20 | 520 | C5b | ok | 7.78 | 66.838 | 0.877 | 520 | 0.9871 |  |
| TelekomCashbackFestnetz_2026_07 | 2 | C4a | ok | 0.46 | 4.348 | 0.084 | 2 | 1.0 |  |
| TelekomCashbackFestnetz_2026_07 | 2 | C4b | ok | 0.46 | 4.348 | 0.1 | 2 | 1.0 |  |
| TelekomCashbackFestnetz_2026_07 | 2 | C5a | ok | 0.08 | 25.0 | 0.009 | 2 | 0.9794 |  |
| TelekomCashbackFestnetz_2026_07 | 2 | C5b | ok | 1.76 | 1.136 | 0.19 | 2 | 0.9794 |  |
| TelekomLeistungsbeschreibungGlasfa | 12 | C4a | ok | 2.2 | 5.455 | 0.164 | 12 | 0.9987 |  |
| TelekomLeistungsbeschreibungGlasfa | 12 | C4b | ok | 1.38 | 8.696 | 0.387 | 12 | 0.9987 |  |
| TelekomLeistungsbeschreibungGlasfa | 12 | C5a | ok | 0.08 | 150.0 | 0.008 | 12 | 0.9727 |  |
| TelekomLeistungsbeschreibungGlasfa | 12 | C5b | ok | 2.28 | 5.263 | 0.91 | 12 | 0.9743 |  |
| TelekomPibMagentaZuhauseL | 1 | C4a | ok | 0.4 | 2.5 | 0.085 | 1 | 1.0 |  |
| TelekomPibMagentaZuhauseL | 1 | C4b | ok | 0.41 | 2.439 | 0.086 | 1 | 1.0 |  |
| TelekomPibMagentaZuhauseL | 1 | C5a | ok | 0.08 | 12.5 | 0.008 | 1 | 1.0 |  |
| TelekomPibMagentaZuhauseL | 1 | C5b | ok | 0.63 | 1.587 | 0.102 | 1 | 0.9967 |  |
| WelgeEulerichCorporateGovernanceMa | 379 | C4a | ok | 27.93 | 13.57 | 0.2 | 379 | 0.8987 |  |
| WelgeEulerichCorporateGovernanceMa | 379 | C4b | ok | 38.2 | 9.921 | 0.626 | 379 | 0.9998 |  |
| WelgeEulerichCorporateGovernanceMa | 379 | C5a | ok | 0.95 | 398.947 | 0.122 | 379 | 0.998 |  |
| WelgeEulerichCorporateGovernanceMa | 379 | C5b | ok | 14.9 | 25.436 | 0.872 | 379 | 0.998 |  |
| WhoEnvironmentalNoiseGuidelinesEur | 181 | C4a | ok | 14.08 | 12.855 | 0.221 | 181 | 0.8217 |  |
| WhoEnvironmentalNoiseGuidelinesEur | 181 | C4b | ok | 20.36 | 8.89 | 0.641 | 181 | 0.9998 |  |
| WhoEnvironmentalNoiseGuidelinesEur | 181 | C5a | ok | 0.52 | 348.077 | 0.114 | 181 | 0.9975 |  |
| WhoEnvironmentalNoiseGuidelinesEur | 181 | C5b | ok | 5.86 | 30.887 | 0.897 | 181 | 0.9976 |  |
| WhoNightNoiseGuidelinesEurope2009 | 184 | C4a | ok | 15.99 | 11.507 | 0.173 | 184 | 0.9819 |  |
| WhoNightNoiseGuidelinesEurope2009 | 184 | C4b | ok | 19.07 | 9.649 | 0.606 | 184 | 0.982 |  |
| WhoNightNoiseGuidelinesEurope2009 | 184 | C5a | ok | 0.51 | 360.784 | 0.111 | 184 | 0.971 |  |
| WhoNightNoiseGuidelinesEurope2009 | 184 | C5b | ok | 13.82 | 13.314 | 0.907 | 184 | 0.9719 |  |
