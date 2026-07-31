# Design: Data-driven test client

Tracking issue: [#1](https://github.com/uppaljs/PyKMS/issues/1)

## Problem

`client.py` hardcoded eight modes (`WindowsVista` … `Windows10`, `Office2010` …
`Office2016`). The README advertises activation through Windows Server 2022–2025,
but the bundled test client could not request any product newer than Windows 10 /
Office 2016, and every new product required hand-editing GUIDs.

## Key finding

Every `KmsItem` in `KmsDataBase.xml` already carries the four values a KMS
request needs:

- `@Id` → KMS counted id (`KMSClientKMSCountedID`)
- `@DefaultKmsProtocol` → protocol major version (4 / 5 / 6)
- parent `AppItem @Id` → `KMSClientAppID`
- child `SkuItem @Id` → `KMSClientSkuID`

The existing hardcoded modes map exactly to these entries, so the client can be
driven entirely from the database that already ships in the repo.

## Design

**Catalog loader** (`client.loadCatalog`) — parses `KmsDataBase.xml` with the
repo's own `xmltok` + `uxml2dict` into a flat list of products, one per
`KmsItem`: `{appId, appName, kmsId, kmsName, major, skus:[(id,name)]}`.
KmsItems with zero SKUs are skipped (nothing to request).

**CLI** (`client.py`)
- `-m/--mode` accepts a legacy alias (`Windows7`, `Windows10`, …) *or* a product
  display name (`"Windows Server 2025"`) *or* a raw KmsItem GUID.
- `--list` enumerates every product and exits.
- `--sku` optionally selects a SKU by GUID or name substring; default = first SKU.
- `RequiredClientCount` = 5 for Office application ids, else 25. `LicenseStatus`
  = 2, minor version = 0 (unchanged behaviour).

**Backwards compatibility** — an `ALIASES` table maps each old mode name to a DB
product display name, so existing invocations keep working. There is no separate
"Windows 11" KmsItem; Windows 11 activates through the Windows 10 KMS counted
ids, so it is already covered.

**Refactor** — the network exchange in `main()` is extracted into `exchange()`
(raises `RuntimeError` on protocol failure; the CLI now exits non-zero) and
`printResult()` (which decodes the ePID/HWID for readable output). This makes the
flow reusable by the test harness.

**Test harness** (`test_client_all.py`) — starts `server.py` on a local port,
then drives a real bind + activation exchange for every catalog product and
verifies the response: V4 → response hash matches; V5/V6 → response decrypts to a
well-formed ePID. Exits non-zero on any failure.

## Result

30/30 products pass: V4 9/9, V5 6/6, V6 15/15.

## Out of scope (separate issues)

Review findings: HWID `strip('0x')` bug, `parseResponse` `NameError`, per-request
XML re-parse, file-descriptor leaks, `Dockerfile` Python 2 base. No `server.py`
changes beyond what the harness needs.
