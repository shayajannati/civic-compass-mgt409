# Tokenomics benchmark (2026-10-26T00:37:44, gpt-6-luna)

| Condition | Routing pass | Avg candidates | Routing in / cached / out tokens | Routing $/call | Routing latency | Letter in / out | Letter $/call |
|---|---|---|---|---|---|---|---|
| baseline_cold | 18/18 | 53.1 | 12701.4 / 0 / 247.1 | $0.001711 | 3.38 s | 463.8 / 482.8 | $0.000288 |
| optimized_cold | 18/18 | 12.8 | 1297.6 / 0 / 159.2 | $0.000242 | 2.49 s | 470.3 / 244.5 | $0.000169 |
| optimized_warm | 18/18 | 12.8 | 1286.6 / 1283.6 / 137.4 | $0.000082 | 3.17 s | 447.7 / 202.8 | $0.000146 |

Lookups: {"zip_lookup_local_sqlite_ms": 0.02, "address_geocode_live_ms": 752.1, "address_geocode_cached_ms": 0.51, "address_method": "address", "address_districts": {"cd": ["CT-3"], "ct_house": ["96"], "ct_senate": ["11"]}}
