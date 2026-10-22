# Project defaults

These stack defaults apply whenever House Rules is installed. Overrides follow INDEX.md,
and an existing coherent project stack also takes precedence over them. Overrides need
no separate approval ritual; record consequential choices and their rationale in the
project's CONTEXT.md. New projects: skill `project-bootstrap`.

## Choose only the components needed

| Need | Default | Why / when to override |
|---|---|---|
| Durable native or systems application, demanding long-lived service | Rust | Prefer native deployment and explicit types/resource control. Choose another stack when its ecosystem or project constraints fit better. Storage durability still requires recovery, migrations, and backups. |
| Ordinary web backend | TypeScript on Node.js | Reuse a language and tooling across backend, browser, and scripts. Use Rust when the service's requirements justify it. |
| Scripts and web libraries | Node.js, with TypeScript where useful | Reuse the project's runtime, dependencies, and types. In a Rust-only project, use existing Rust tooling or simple shell instead of adding Node for one script. |
| Browser frontend and visual prototype | Static Svelte + TypeScript, Vite, plain CSS | Simple asset deployment. Add SSR or a framework/service when a concrete product need justifies it; keep an existing UI stack. |
| Browser automation and screenshots | A dedicated headless browser, such as Chrome for Testing or Playwright's headless shell | Keeps tests and UI checks independent of the operator's installed browser and profile. Use a full browser build only when a check needs a feature the headless build lacks. |
| Data analysis or scientific work | Python or the established domain ecosystem | Libraries and workflow can justify a different language, including Clojure. These can be maintained and shipped; they are not confined to throwaway code. |
| Mobile application | Native or Flutter | Choose for target platforms and team constraints; a web wrapper is acceptable when it meets the actual product needs. |
| Service deployment | Backends runnable in OCI containers on any compliant runtime (not Docker-specific), on a VPS (Hetzner by default) or a cloud provider | Preserve a practical VPS path by default; managed or platform-specific services are valid project choices. Static sites and small scripts need no container. |

Prefer one language when it meets the requirements. Before adding another, state the
concrete benefit and build/deployment/maintenance cost. A full Rust + Node + Svelte stack
is not required for a small tool. Reuse the pinned project toolchain; for new Node work,
prefer a supported LTS release, ESM, pnpm, and minimal dependencies. Do not require the
`ts-node` package merely because TypeScript executes on Node.

## Storage

For document/vault products, start with Markdown and structured metadata; use an
append-only log when event history is intrinsic. For transactional application state,
use a database. Choose the storage and rebuild equivalence required by the product; do
not force every application into a Markdown vault.

Architecture principles (canonical data, end-state design, tenancy) live in
`skills/design-canon/SKILL.md`; Rust-specific tooling defaults live in
`skills/rust-canon/SKILL.md`.

## Naming defaults

These defaults supply the naming conventions that the
[writing rules](rules/writing.md#language) require each specification and codebase to
declare. A project adopts them in its bible; the writing rules say what it then declares.

### Inside code

Follow each language's community standard.

- **Rust:** types and traits `UpperCamelCase`; functions, variables and modules
  `snake_case`; constants `SCREAMING_SNAKE_CASE`. Conversions are `as_`, `to_` and
  `into_`; getters have no `get_` prefix.
- **TypeScript and JavaScript:** types `PascalCase`; variables and functions `camelCase`.
- **Python:** PEP 8. Exception classes end in `Error`.
- **Svelte:** components `PascalCase.svelte`.
- **SQL:** `snake_case`.
- **Acronyms:** one word in Rust, TypeScript and .NET: `Id`, `HttpClient`. Python follows
  PEP 8.
- **File names:** each language's convention. Rust and Python module files are
  `snake_case`. Documents and slugs stay kebab-case under
  [STRUCTURE.md §Naming rules](STRUCTURE.md#naming-rules).

### Public names that cross language boundaries

- **JSON and wire fields:** `snake_case`. TypeScript types keep the wire names
  unchanged; set the ESLint `camelcase` rule to `properties: "never"`.
- **API operations:** `resource.verb` with a plural noun: `records.update`.
- **Error variants:** `UpperCamelCase`, subject then state: `QuotaExceeded`. A variant may
  start with one of the qualifiers `Invalid`, `Not`, `Already`, `Missing`, `Unsupported` or
  `Unknown`: `InvalidEdit`, `NotFound`.
- **Error codes on the wire:** the variant in `snake_case`: `InvalidEdit` → `invalid_edit`.
- **Status values:** `snake_case` words. `active` for usable, a past participle for
  finished (`succeeded`), a present participle for in progress (`running`). The field
  is named `status`.
- **Settings:** `snake_case`, subject then bound then unit: `upload_max_bytes`.
- **Numbers:** every name that holds a number carries its unit: `_bytes`, `_ms`, `_count`.
- **Booleans:** no negated names such as `no_cache`. Name a boolean so that `false` is the
  safe default. Wire names are plain adjectives: `enabled`, not `is_enabled`.
- **Timestamps:** `_at` after a past participle: `created_at`. The definition of a name
  ending in `_until` states whether its bound is inclusive. Calendar dates end in `_date`. Durations carry a
  unit suffix: `timeout_ms`.
- **Environment variables:** `SCREAMING_SNAKE_CASE` with a product prefix: `ACME_LOG_LEVEL`.
- **Events:** `snake_case`, subject then past participle: `record_created`.
- **Collections and tables:** singular: `invoice`.
- **Version suffixes:** integer major versions only: `_v1`, never `_v1_2`.
- **Filler words:** none, as the writing rules require.
