# Tokenomics benchmark (2026-10-26T00:28:55, gpt-6-luna)

| Condition | Routing pass | Avg candidates | Routing in / cached / out tokens | Routing $/call | Routing latency | Letter in / out | Letter $/call |
|---|---|---|---|---|---|---|---|
| baseline_cold | 17/18 | 53.1 | 12683.2 / 0 / 239.2 | $0.001705 | 4.6 s | 461.7 / 421.7 | $0.000257 |
| optimized_cold | 15/18 | 12.8 | 1279.4 / 0 / 158.5 | $0.000239 | 2.8 s | 461.2 / 233.2 | $0.000163 |
| optimized_warm | 16/18 | 12.8 | 1268.6 / 1265.6 / 147.1 | $0.000087 | 2.56 s | 453 / 224.8 | $0.000158 |

Lookups: {"zip_lookup_local_sqlite_ms": 0.02, "address_geocode_live_ms": 791.3, "address_geocode_cached_ms": 0.44, "address_method": "address", "address_districts": {"cd": ["CT-3"], "ct_house": ["96"], "ct_senate": ["11"]}}
