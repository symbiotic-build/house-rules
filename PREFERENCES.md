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

The naming defaults a project can adopt live in
[prompts/skills/naming-defaults.md](prompts/skills/naming-defaults.md), so compiled
reviewers and implementers receive them.
