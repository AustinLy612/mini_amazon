# Milestone 3 verification

Executed on November 1, 2026 with Python 3.12.3 and an isolated PostgreSQL 16.15 instance listening on loopback. Existing course/application databases were not replaced.

## Results

- 52 tests passed, plus 15 subtests: 38 SQLite route/SQL/template tests, 10 native PostgreSQL seller tests and 4 native PostgreSQL milestone-query tests. Five Python 3.12 SQLite datetime-adapter deprecation warnings do not affect the assertions.
- All four role requirements have SQL queries, HTML results and JSON endpoints. The private ID-based endpoints validate ownership; guest and cross-account requests are rejected.
- Verified final order prices and delivery snapshots, multi-seller buyer totals, all three fulfillment states, empty results, top-k price ties/invalid input, persistent carts, zero stock, removed listings, CSRF and seller isolation.
- Browser verification at http://127.0.0.1:8080: entered k=2; received an HTML price-sorted result; logged in as the demo buyer; opened purchase history and order details; viewed the saved cart; switched to the demo seller; searched inventory for vanilla and reset the filter. Console error/warning inspection returned no relevant entries. Default desktop viewport was checked; mobile was not tested in this pass.
- The Top-k HTML form was corrected to target the HTML route rather than the JSON route. A regression assertion covers its action URL.

## Reproduce

Install runtime dependencies and pytest. Set DB_HOST, DB_PORT, DB_USER and DB_PASSWORD for a development PostgreSQL server. The first command below needs no native test database; the opt-in checks require separately named databases seeded through the existing safe setup tool.

```text
python -m pytest -q
python tools/setup_sellers.py --database mini_amazon_sellers_verify_m3 --no-config
python tools/setup_sellers.py --database mini_amazon_m3_demo --demo
```

Then set these environment variables and run `python -m pytest -q`:

```text
SELLERS_POSTGRES_TEST=1
SELLERS_TEST_DB=mini_amazon_sellers_verify_m3
M3_POSTGRES_TEST=1
M3_TEST_DB=mini_amazon_m3_demo
```

The seller PostgreSQL suite resets data only in its explicitly guarded verification database; it never accepts the normal application database as its reset target. The M3 PostgreSQL tests read the separately seeded demo database without modifying its fixtures. Setup refuses to overwrite an existing database. Without opt-in variables, native PostgreSQL tests are skipped explicitly.

## Remaining submission step

The course's team-narrated video is not yet supplied. Record the flow in DEMO.md, publish a viewable link, add it to README.txt, and rebuild the submission package. The code does not implement final-stage checkout/profile/catalog editing; these are not the four M3 required queries. The synthetic paid-order fixtures do not imply that checkout exists.
