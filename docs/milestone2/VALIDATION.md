# Validation record — 2026-10-08

## Verified in this task
- Branch: grace-wishlist; original skeleton commit bf78ef7, previous Carts commit 253dbec.
- Course containers: container-ubuntu-1 and container-postgres-1. Existing development data was preserved.
- `poetry lock --no-update` and `poetry install --no-root` succeeded; humanize 4.16.0 added. The repo ignores poetry.lock, so teammates resolve dependencies using Poetry themselves.
- `poetry run python -m unittest discover -s tests -v`: **11 tests passed**, seven Carts tests and four Wishlist tests, SQLite-backed real SQL/routes/templates. Wishlist tests include a real login form/password check with CSRF enabled.
- Created a separate PostgreSQL database `mini_amazon_m2_verify_aligned_20261008`; applied db/create.sql, db/load.sql from db/data, db/carts_schema.sql, and db/carts_demo.sql successfully.
- `tests/postgres_smoke.py` passed: real login, cart HTML/JSON/totals, wishlist insert and HTML redirect, missing-product 404, missing-CSRF 400, guest restriction, account isolation, fresh application/connection persistence, and six invalid-write constraint checks, listing deletion, snapshot names and order-line identity/uniqueness.
- The smoke test creates one extra wishlist row per run in the verification database only. It refuses databases outside the verification naming prefix. It does not drop databases or modify existing development databases.

- Final PDF regenerated from CARTS_DESIGN.md; all four rendered pages reviewed for clipping/layout.
- `git diff --check` passed; PDFs are marked binary via .gitattributes.

## Limits
- In-app browser automation failed to attach; no assistant browser-click verification is claimed. The actual PostgreSQL-backed Flask HTTP handlers and HTML rendering were tested through Flask test clients. A local server was started at http://localhost:8080 for the student walkthrough.
- Recreating the Flask application/connection is verified; a physical PostgreSQL server restart was not tested.
- No checkout/concurrency/payment claim: those features are design-only for M2.
- Personal student understanding and other members' tutorial completion cannot be certified by automated tests.
- Upload is handled separately; this file records validation, not remote publication status.

## Repeat inside the course container
```bash
cd ~/shared/mini_amazon
poetry install --no-root
poetry run python -m unittest discover -s tests -v
DB_NAME=mini_amazon_m2_verify_aligned_20261008 poetry run python -c 'import runpy; runpy.run_path("tests/postgres_smoke.py", run_name="__main__")'
```
The PostgreSQL command expects the verification DB and small fixtures prepared as described above. Do not run schema initialization twice against an existing database.

## Team-contract alignment
Orders/OrderItems follow Leyang Han's snapshot names and id + UNIQUE design. Cart inventory/price behavior follows Tiancheng Yu's positive-price, physical listing removal design. Cart query no longer depends on active/available flags. Shared Users bootstrap fields remain compatibility adapters; full Users/Products migrations belong to their owners.

## Legacy migration verification
A separate mini_amazon_m2_verify_migration_20261008 database was initialized with
commit 253dbec's original Carts schema and fixtures. The one-time
migrate_carts_m2_contract.sql completed successfully, followed by the same passing
PostgreSQL smoke test. Existing personal development databases were not migrated.
