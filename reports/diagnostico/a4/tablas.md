| modelo | pesos | subconjunto | imagenes | personas | imagenes_sin_persona | map50 | map50_95 | precision | recall |
|---|---|---|---|---|---|---|---|---|---|
| fusion | best.pt | todas | 442 | 500 | 137 | 0.3749 | 0.1675 | 0.5592 | 0.3704 |
| fusion | best.pt | 210417_MtErie_Enterprise_0007 | 169 | 289 | 0 | 0.6004 | 0.2740 | 0.6781 | 0.5225 |
| fusion | best.pt | 210924_FHL_Enterprise_0134 | 273 | 211 | 137 | 0.0825 | 0.0305 | 0.2776 | 0.1659 |
| fusion | best.pt | solo_termica | 68 | 75 | 0 | 0.3412 | 0.1514 | 0.5854 | 0.3867 |
| fusion | best.pt | resto | 374 | 425 | 137 | 0.3873 | 0.1749 | 0.5770 | 0.3671 |
| fusion | last.pt | todas | 442 | 500 | 137 | 0.2500 | 0.1111 | 0.5007 | 0.2700 |
| fusion | last.pt | 210417_MtErie_Enterprise_0007 | 169 | 289 | 0 | 0.3920 | 0.1966 | 0.6077 | 0.3529 |
| fusion | last.pt | 210924_FHL_Enterprise_0134 | 273 | 211 | 137 | 0.0727 | 0.0149 | 0.3956 | 0.1517 |
| fusion | last.pt | solo_termica | 68 | 75 | 0 | 0.3288 | 0.0856 | 0.7245 | 0.3733 |
| fusion | last.pt | resto | 374 | 425 | 137 | 0.2424 | 0.1179 | 0.4473 | 0.2588 |

| modelo | pesos | subconjunto | tramo | personas | map50_pycocotools |
|---|---|---|---|---|---|
| fusion | best.pt | todas | todas | 500 | 0.3790 |
| fusion | best.pt | todas | <8 | 3 | 0.0000 |
| fusion | best.pt | todas | 8-12 | 112 | 0.1023 |
| fusion | best.pt | todas | 12-20 | 97 | 0.2558 |
| fusion | best.pt | todas | 20-32 | 55 | 0.2267 |
| fusion | best.pt | todas | >=32 | 233 | 0.6212 |
| fusion | best.pt | 210417_MtErie_Enterprise_0007 | todas | 289 | 0.5994 |
| fusion | best.pt | 210417_MtErie_Enterprise_0007 | <8 | 0 | — |
| fusion | best.pt | 210417_MtErie_Enterprise_0007 | 8-12 | 0 | — |
| fusion | best.pt | 210417_MtErie_Enterprise_0007 | 12-20 | 1 | 0.0000 |
| fusion | best.pt | 210417_MtErie_Enterprise_0007 | 20-32 | 55 | 0.4721 |
| fusion | best.pt | 210417_MtErie_Enterprise_0007 | >=32 | 233 | 0.6466 |
| fusion | best.pt | 210924_FHL_Enterprise_0134 | todas | 211 | 0.0842 |
| fusion | best.pt | 210924_FHL_Enterprise_0134 | <8 | 3 | 0.0000 |
| fusion | best.pt | 210924_FHL_Enterprise_0134 | 8-12 | 112 | 0.1462 |
| fusion | best.pt | 210924_FHL_Enterprise_0134 | 12-20 | 96 | 0.3300 |
| fusion | best.pt | 210924_FHL_Enterprise_0134 | 20-32 | 0 | — |
| fusion | best.pt | 210924_FHL_Enterprise_0134 | >=32 | 0 | — |
| fusion | best.pt | solo_termica | todas | 75 | 0.3456 |
| fusion | best.pt | solo_termica | <8 | 3 | 0.0000 |
| fusion | best.pt | solo_termica | 8-12 | 22 | 0.1677 |
| fusion | best.pt | solo_termica | 12-20 | 40 | 0.6553 |
| fusion | best.pt | solo_termica | 20-32 | 3 | 0.0842 |
| fusion | best.pt | solo_termica | >=32 | 7 | 0.2666 |
| fusion | best.pt | resto | todas | 425 | 0.3904 |
| fusion | best.pt | resto | <8 | 0 | — |
| fusion | best.pt | resto | 8-12 | 90 | 0.0839 |
| fusion | best.pt | resto | 12-20 | 57 | 0.0710 |
| fusion | best.pt | resto | 20-32 | 52 | 0.2436 |
| fusion | best.pt | resto | >=32 | 226 | 0.6357 |
| fusion | last.pt | todas | todas | 500 | 0.2554 |
| fusion | last.pt | todas | <8 | 3 | 0.0000 |
| fusion | last.pt | todas | 8-12 | 112 | 0.0193 |
| fusion | last.pt | todas | 12-20 | 97 | 0.2852 |
| fusion | last.pt | todas | 20-32 | 55 | 0.1880 |
| fusion | last.pt | todas | >=32 | 233 | 0.4179 |
| fusion | last.pt | 210417_MtErie_Enterprise_0007 | todas | 289 | 0.3931 |
| fusion | last.pt | 210417_MtErie_Enterprise_0007 | <8 | 0 | — |
| fusion | last.pt | 210417_MtErie_Enterprise_0007 | 8-12 | 0 | — |
| fusion | last.pt | 210417_MtErie_Enterprise_0007 | 12-20 | 1 | 0.0000 |
| fusion | last.pt | 210417_MtErie_Enterprise_0007 | 20-32 | 55 | 0.3872 |
| fusion | last.pt | 210417_MtErie_Enterprise_0007 | >=32 | 233 | 0.4283 |
| fusion | last.pt | 210924_FHL_Enterprise_0134 | todas | 211 | 0.0745 |
| fusion | last.pt | 210924_FHL_Enterprise_0134 | <8 | 3 | 0.0000 |
| fusion | last.pt | 210924_FHL_Enterprise_0134 | 8-12 | 112 | 0.0400 |
| fusion | last.pt | 210924_FHL_Enterprise_0134 | 12-20 | 96 | 0.2947 |
| fusion | last.pt | 210924_FHL_Enterprise_0134 | 20-32 | 0 | — |
| fusion | last.pt | 210924_FHL_Enterprise_0134 | >=32 | 0 | — |
| fusion | last.pt | solo_termica | todas | 75 | 0.3304 |
| fusion | last.pt | solo_termica | <8 | 3 | 0.0000 |
| fusion | last.pt | solo_termica | 8-12 | 22 | 0.0099 |
| fusion | last.pt | solo_termica | 12-20 | 40 | 0.6319 |
| fusion | last.pt | solo_termica | 20-32 | 3 | 0.0842 |
| fusion | last.pt | solo_termica | >=32 | 7 | 0.2409 |
| fusion | last.pt | resto | todas | 425 | 0.2455 |
| fusion | last.pt | resto | <8 | 0 | — |
| fusion | last.pt | resto | 8-12 | 90 | 0.0246 |
| fusion | last.pt | resto | 12-20 | 57 | 0.0872 |
| fusion | last.pt | resto | 20-32 | 52 | 0.2029 |
| fusion | last.pt | resto | >=32 | 226 | 0.4256 |

| modelo | pesos | conf | grupo | personas | detectadas | recall | falsos_positivos | imagenes |
|---|---|---|---|---|---|---|---|---|
| fusion | best.pt | 0.250 | todas | 500 | 152 | 0.304 | 84 | 442 |
| fusion | best.pt | 0.250 | 210417_MtErie_Enterprise_0007 | 289 | 136 | 0.471 | 50 | 169 |
| fusion | best.pt | 0.250 | 210924_FHL_Enterprise_0134 | 211 | 16 | 0.076 | 34 | 273 |
| fusion | best.pt | 0.250 | solo_termica | 75 | 15 | 0.200 | 10 | 68 |
| fusion | best.pt | 0.250 | resto | 425 | 137 | 0.322 | 74 | 374 |
| fusion | best.pt | 0.250 | tramo <8 | 3 | 0 | 0.000 | — | — |
| fusion | best.pt | 0.250 | tramo 8-12 | 112 | 4 | 0.036 | — | — |
| fusion | best.pt | 0.250 | tramo 12-20 | 97 | 12 | 0.124 | — | — |
| fusion | best.pt | 0.250 | tramo 20-32 | 55 | 19 | 0.345 | — | — |
| fusion | best.pt | 0.250 | tramo >=32 | 233 | 117 | 0.502 | — | — |
| fusion | best.pt | 0.500 | todas | 500 | 92 | 0.184 | 22 | 442 |
| fusion | best.pt | 0.500 | 210417_MtErie_Enterprise_0007 | 289 | 87 | 0.301 | 8 | 169 |
| fusion | best.pt | 0.500 | 210924_FHL_Enterprise_0134 | 211 | 5 | 0.024 | 14 | 273 |
| fusion | best.pt | 0.500 | solo_termica | 75 | 4 | 0.053 | 0 | 68 |
| fusion | best.pt | 0.500 | resto | 425 | 88 | 0.207 | 22 | 374 |
| fusion | best.pt | 0.500 | tramo <8 | 3 | 0 | 0.000 | — | — |
| fusion | best.pt | 0.500 | tramo 8-12 | 112 | 2 | 0.018 | — | — |
| fusion | best.pt | 0.500 | tramo 12-20 | 97 | 3 | 0.031 | — | — |
| fusion | best.pt | 0.500 | tramo 20-32 | 55 | 10 | 0.182 | — | — |
| fusion | best.pt | 0.500 | tramo >=32 | 233 | 77 | 0.330 | — | — |
| fusion | last.pt | 0.250 | todas | 500 | 116 | 0.232 | 88 | 442 |
| fusion | last.pt | 0.250 | 210417_MtErie_Enterprise_0007 | 289 | 94 | 0.325 | 46 | 169 |
| fusion | last.pt | 0.250 | 210924_FHL_Enterprise_0134 | 211 | 22 | 0.104 | 42 | 273 |
| fusion | last.pt | 0.250 | solo_termica | 75 | 24 | 0.320 | 9 | 68 |
| fusion | last.pt | 0.250 | resto | 425 | 92 | 0.216 | 79 | 374 |
| fusion | last.pt | 0.250 | tramo <8 | 3 | 0 | 0.000 | — | — |
| fusion | last.pt | 0.250 | tramo 8-12 | 112 | 0 | 0.000 | — | — |
| fusion | last.pt | 0.250 | tramo 12-20 | 97 | 22 | 0.227 | — | — |
| fusion | last.pt | 0.250 | tramo 20-32 | 55 | 18 | 0.327 | — | — |
| fusion | last.pt | 0.250 | tramo >=32 | 233 | 76 | 0.326 | — | — |
| fusion | last.pt | 0.500 | todas | 500 | 89 | 0.178 | 51 | 442 |
| fusion | last.pt | 0.500 | 210417_MtErie_Enterprise_0007 | 289 | 77 | 0.266 | 18 | 169 |
| fusion | last.pt | 0.500 | 210924_FHL_Enterprise_0134 | 211 | 12 | 0.057 | 33 | 273 |
| fusion | last.pt | 0.500 | solo_termica | 75 | 13 | 0.173 | 6 | 68 |
| fusion | last.pt | 0.500 | resto | 425 | 76 | 0.179 | 45 | 374 |
| fusion | last.pt | 0.500 | tramo <8 | 3 | 0 | 0.000 | — | — |
| fusion | last.pt | 0.500 | tramo 8-12 | 112 | 0 | 0.000 | — | — |
| fusion | last.pt | 0.500 | tramo 12-20 | 97 | 12 | 0.124 | — | — |
| fusion | last.pt | 0.500 | tramo 20-32 | 55 | 12 | 0.218 | — | — |
| fusion | last.pt | 0.500 | tramo >=32 | 233 | 65 | 0.279 | — | — |
