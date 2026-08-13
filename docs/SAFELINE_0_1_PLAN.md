# SafeLine Manager 0.1 plan

## Goal

SafeLine Manager `0.1.x` establishes a legally and technically controlled fork
without changing the proven VPN core behavior. It is complete when SafeLine can
build, test and install a pinned baseline on a disposable Linux VPS through its
own release channel.

## Phase 0: decisions that precede product work

1. Obtain a documented license decision for the Manager, Python panel, compiled
   frontend and bundled assets. For the Python panel this may require written
   permission, qualified legal clearance, or replacement of the affected code.
2. Create a SafeLine-owned repository and configure it as `origin`; retain the
   official Hiddify repository as `upstream`.
3. Decide which Linux distribution and versions SafeLine will support. The
   current scripts assume an Ubuntu/Debian-style system and privileged systemd
   access.
4. Establish secret-handling rules. No production database passwords, API keys,
   Telegram tokens or VPS private keys belong in Git.

## Phase 1: make the inherited behavior testable

Add a CI pipeline with these gates:

- Python syntax, formatting and static checks;
- unit tests for `User.is_active`, quota resets and API schemas;
- API contract tests for admin user CRUD and user profile/config endpoints;
- fixture-based rendering of `current.json` into Xray and Hiddify Core configs;
- real `xray run -test` and `sing-box check`/Hiddify Core validation;
- clean-VPS install smoke test;
- backup/restore and rollback test;
- dependency/license and secret scanning.

Before changing protocols, capture golden outputs for one active VLESS Reality
user, one expired user and one quota-exhausted user.

## Phase 2: separate the SafeLine product boundary

Introduce a small SafeLine configuration layer for:

- product name and version;
- logo, favicon, colors and support links;
- public URLs and Telegram bot identity;
- release/update endpoints;
- enabled product capabilities.

At this stage keep compatibility identifiers such as the `hiddifypanel` Python
package and `/opt/hiddify-manager` path internal. Renaming them globally adds
risk without improving the user experience.

Also replace the inherited updater so it can only consume signed or checksummed
SafeLine artifacts pinned to an explicit version.

## Phase 3: build the SafeLine user portal from source

Create a reproducible frontend project that consumes the existing user API and
shows only the SafeLine product surface:

- account status;
- remaining days and traffic;
- connection/import button;
- available SafeLine locations;
- support and Telegram links.

The build should generate hashed assets and a manifest consumed by the Flask
template. No code should search and patch a generated `index-*.js` file.

## Phase 4: add a SafeLine API facade and bot integration

Do not give the Telegram bot the owner's UUID/API key. Add scoped credentials
and an auditable SafeLine service boundary around inherited operations:

- create a user idempotently;
- activate, suspend, extend and change quota;
- return subscription/profile links;
- return usage and expiry status;
- record which bot/payment event caused a mutation.

The inherited admin CRUD API can implement the first adapter, but the public
contract should use SafeLine terminology and remain stable if the backend is
later replaced.

## Phase 5: add product data instead of overloading `User`

Add explicit SafeLine concepts:

- `Plan` for price, duration, quota and allowed locations;
- `Subscription` for lifecycle and entitlement dates;
- `Payment` or an external payment reference with idempotency keys;
- `AuditEvent` for administrative and bot actions;
- `Node` and `NodeHealth` when multi-node work begins.

The inherited `User` record should remain the runtime VPN identity. Product and
billing state should not be encoded only in `package_days`, `start_date` and
`usage_limit`.

## Phase 6: simplify protocols safely

Start by disabling unused capabilities through configuration and the UI. Remove
code only after rendered-config and subscription tests prove that SafeLine's
VLESS Reality path is unaffected. The likely retained path is:

```text
SafeLine user -> VLESS Reality subscription -> Xray runtime -> usage driver
```

Keep Hiddify Core/sing-box temporarily if it is required for clients or
subscription generation; make its removal a measured decision, not an initial
cleanup task.

## Phase 7: design node management

Treat remote nodes as new work. The first usable version needs:

- scoped node enrollment credentials;
- heartbeat and version reporting;
- health and capacity state;
- deterministic user/config rollout;
- per-node usage reconciliation;
- draining and removal;
- timeout, retry and failure semantics;
- audit logs and rollback.

Existing parent/child APIs can be mined for schemas and synchronization logic,
but the current admin UI explicitly disables remote nodes.

## Definition of done for 0.1.0

- The license decision is recorded and compatible with the intended SafeLine
  use.
- `origin` is SafeLine-owned; `upstream` remains the pinned reference.
- Dependencies and build artifacts are pinned and checksummed.
- CI validates Python, APIs and generated VPN configurations.
- A disposable supported VPS can install, upgrade, back up, restore and roll
  back the SafeLine baseline.
- The updater cannot silently replace SafeLine with an upstream Hiddify release.
- No functional VPN-core behavior has changed without a characterization test.

Only after this foundation should work begin on the user-visible `0.2.0`
SafeLine interface.
