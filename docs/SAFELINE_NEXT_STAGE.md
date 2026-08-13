# SafeLine next product stage

The next stage should keep the same rule: no VPN-core, UUID, quota, statistics,
Reality, routing, DNS, outbound, API-statistics, service-name, or database
changes until separately reviewed.

## 1. Linux installation smoke test

- install the current branch on a disposable supported VPS;
- verify login, administrator pages, modern profile page, PWA manifest, static
  asset routing, custom administrator branding, and Telegram messages;
- capture screenshots and HTTP/API contract fixtures;
- verify upgrade, backup, restore, rollback, and service restarts.

## 2. SafeLine-controlled update and release channel

- stop product updates from following moving Hiddify release/branch endpoints;
- publish versioned SafeLine artifacts from `Pay4eck/SafeLine-Manager`;
- require checksums/signatures and an explicit rollback target;
- continue to fetch Hiddify only through the read-only `upstream` remote for
  reviewed merges.

## 3. Replace the legacy DOM compatibility shim with template overlays

- add reviewed SafeLine-owned overlays for the active login/admin/error
  templates and localization catalog;
- retain explicit “Based on Hiddify Manager” attribution and all license files;
- keep real Hiddify client names/download links accurate;
- remove `branding.js` only after page-level tests prove equivalent coverage.

## 4. Decide Panel and frontend source ownership

- create a SafeLine-controlled Panel fork/submodule reference or a documented
  patch-application pipeline before changing Panel Python source;
- create a dedicated SafeLine frontend fork or vendor the exact source snapshot
  so builds do not depend indefinitely on repository availability;
- record the formal license decision before any paid/commercial launch.

## 5. Only then design the product API boundary

- introduce scoped, revocable SafeLine credentials instead of exposing UUIDs as
  general API keys;
- add idempotent user lifecycle operations and audit events for bot/payment
  actions;
- keep inherited API paths and `Hiddify-API-Key` as compatibility interfaces
  until consumers migrate.
