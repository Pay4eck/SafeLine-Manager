# SafeLine Manager 0.1.0 branding audit

## Scope and method

The audit covers the Manager repository and the complete checked-out Panel
submodule pinned at Hiddify Panel `v12.3.3`.  It scans text, binary ASCII
tokens, and Hiddify-named files/directories.  Generated test/runtime folders
and the audit reports themselves are excluded to avoid self-reference.

The reproducible inventory is in `BRANDING_AUDIT_INVENTORY.json`; every record
contains a path, line (where meaningful), match count, category, sample, and
classification reason.  Regenerate it with:

```text
python safeline/tools/branding_audit.py
```

Current inventory summary:

| Category | Records | Token matches | Unique paths |
| --- | ---: | ---: | ---: |
| A — safe presentation replacements | 903 | 1,861 | 71 |
| B — hide/contain, retain compatibility or provenance | 3,666 | 4,441 | 239 |
| C — compatibility-critical identifiers | 1,177 | 1,406 | 287 |
| **Total** | **5,746** | **7,708** | **449 distinct paths overall** |

The high B count is mainly historical release notes (`HISTORY.md`) and
translations.  Counts are intentionally not reduced by a repository-wide
replacement.

## A. Safe to replace at the presentation boundary

These references are product chrome, copy, or assets.  They do not identify a
protocol, database object, service, package, or upstream component:

- modern profile-page title, meta description, product heading, loading view,
  footer, social links, logo, favicon, and QR logo;
- legacy user/admin/login/error template titles, splash/side-bar logos,
  `HiddifyManager` labels, footer copyright, repository/social links, and PWA
  install wording;
- default `/api/v2/user/me/` values (`brand_title`, `brand_icon_url`, default
  administrator message/link), while preserving administrator custom branding;
- PWA manifest name, short name, description, and icon;
- OpenAPI product description/contact/title, while preserving the inherited
  license object and the compatibility header name;
- the two Telegram bot messages that say “Your hiddify information/instance”.

SafeLine 0.1 implements these through `safeline/branding.py`,
`safeline/static/brand/branding.js`, and the source-built modern frontend.
The original Panel templates/translations remain unchanged in the pinned
submodule, but the active web entrypoint installs the SafeLine overlay.

No standalone email delivery/template subsystem with Hiddify-branded content
was found in this revision.  Telegram notification copy is the only dedicated
notification surface found by the audit.

## B. Hide or contain now; do not rename the underlying reference yet

These occurrences are not SafeLine product chrome, or are coupled to an
upstream workflow.  They remain deliberately visible only when accuracy or
attribution requires it:

- real compatible client names and packages such as Hiddify Next, HiddifyNG,
  HiddifyN, their store IDs, download filenames, and GitHub release URLs;
- upstream documentation/update/download URLs used by installer and updater
  scripts; their human-facing banners can be redesigned later, but their source
  references must not be rewritten as if SafeLine hosted the artifacts;
- the original `index-ccb9873c.js`, old logos, templates, and translations in
  the pinned Panel submodule.  They are retained as the upstream baseline but
  are no longer the active modern profile page;
- README, history, audit, source comments, fixture provenance, and upstream
  repository references;
- visible attribution.  The SafeLine frontend says “Based on Hiddify Manager”
  and links to the upstream project; it is not replaced with a misleading
  SafeLine-only copyright claim.

The legacy compatibility script removes obsolete Hiddify social/product links
from product chrome and redirects Manager help/repository chrome to the
SafeLine fork.  It intentionally does not rewrite client download links.

## C. Critical internal identifiers — do not rename in 0.1

Changing any of these can break installation, upgrades, API clients, database
state, traffic accounting, or Xray integration:

- Python package/module `hiddifypanel`, all imports, extension strings, entry
  points, and the `hiddify` internal helper module;
- install/config roots such as `/opt/hiddify-manager` and their backup/log
  paths;
- Linux user/group `hiddify-panel`;
- systemd units including `hiddify-panel.service`,
  `hiddify-panel-background-tasks.service`, `hiddify-xray.service`,
  `hiddify-nginx.service`, `hiddify-haproxy.service`,
  `hiddify-singbox.service`, Redis/WARP/DNSTT/SSH companion units, and related
  dependency names;
- database/schema/table identifiers and migration history owned by
  `hiddifypanel`;
- API paths and the `Hiddify-API-Key` request/security-scheme header;
- `HIDDIFY_*` environment/config variables;
- `hiddify://` deep links, Hiddify client user-agent detection, and real client
  package IDs;
- Xray statistics email keys such as `<uuid>@hiddify.com`.  They join rendered
  users to Xray usage counters and must not change during a branding stage;
- Docker service/image/label names and install/update component identifiers;
- the `hiddify-panel` directory/submodule path and upstream source remotes.

The root Git remote policy is separate from those compatibility identifiers:
`origin` is `Pay4eck/SafeLine-Manager`; `upstream` is the read-only Hiddify
source and has push disabled.

## Assets, licenses, and attribution

No license file, copyright notice, or upstream attribution was edited.  The
Manager root license and the Panel submodule license are not identical; the
Panel submodule declares CC BY-NC-SA 4.0.  The exact frontend source commit has
no separate license file.  SafeLine therefore takes the conservative approach:
retain the Panel license unchanged and keep explicit upstream attribution in
the active frontend and legacy footer.

## Resulting boundary

The active presentation now flows through a single SafeLine-owned boundary:

```text
hiddify-panel/app.py
  -> safeline.branding.create_app()
  -> unchanged hiddifypanel.create_app()
  -> SafeLine template/static/API/manifest/notification overlay
```

VPN generation, Reality/Xray rendering, UUIDs, limits, statistics, routing,
outbounds, DNS, logging, API statistics, service names, and network behavior
are untouched.
