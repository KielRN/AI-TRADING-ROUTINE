# Coinbase API Setup — Status & Fix

## Status: WORKING

All subcommands verified against live `api.coinbase.com/api/v3/brokerage`:
`account`, `position`, `quote`, `orders` return 200s.

## Root Cause

`coinbase-advanced-py` v1.8.2 (latest on PyPI) only signs JWTs with **ES256 + a
PEM-formatted EC P-256 key**. Coinbase now issues **Ed25519** CDP keys:

- `id` — UUID (used as JWT `sub` / `kid`)
- `privateKey` — 64-byte base64 (32-byte Ed25519 seed + 32-byte public key)

These need **EdDSA** JWT signing. The earlier 401s were all ES256 attempts.

## Fix

`scripts/coinbase.py` patches `coinbase.jwt_generator.build_jwt` before the
`RESTClient` is instantiated. New `build_jwt`:

- If secret contains `BEGIN` → load as PEM, sign **ES256** (old-format keys).
- Otherwise → base64-decode, take first 32 bytes, build `Ed25519PrivateKey`,
  sign **EdDSA** (new CDP keys).

JWT payload is unchanged: `sub = kid = UUID`, `iss = "cdp"`, 120s expiry,
optional `uri` claim for REST, random `nonce` header.

## `.env` Format

```
COINBASE_API_KEY=<uuid from cdp_api_key.json "id" field>
COINBASE_API_SECRET=<base64 string from "privateKey" field>
```

No PEM wrapping, no org path. Raw values.

## Related Fixes in `scripts/coinbase.py`

- `cmd_quote`: `pb.get("time")` → `pb["time"]` (SDK returns `PriceBook` objects
  that support `__getitem__` but not `.get`).
- `cmd_position`: now sums all BTC wallets instead of breaking on the first
  (matches `cmd_account`; BTC can be split across primary + vault).

## Files

- `scripts/coinbase.py` — patch + SDK wrapper
- `cdp_api_key.json` — gitignored; keep for reference
- `.env` — keys live here
