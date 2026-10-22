## Naming defaults

These defaults supply the naming conventions that the
[writing rules](../../rules/writing.md#language) require each specification and codebase
to declare. A project adopts them in its bible; the writing rules say what it then
declares. When the project's bible adopts them, apply them to every name the change adds
or renames, together with the overrides the bible lists. A project that has not adopted
them follows only its own declared conventions.

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
  `snake_case`. Documents and slugs stay kebab-case, as House Rules `STRUCTURE.md`
  §Naming rules sets.

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
