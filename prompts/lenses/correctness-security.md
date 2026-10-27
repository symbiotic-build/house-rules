## Lens: correctness and security

Look for:
- Wrong results: off-by-one and boundary values, empty and maximum inputs, wrong
  units, inverted conditions, unhandled enum cases, lossy conversions and overflow.
- Broken invariants: a state the code promises never to reach that some path reaches;
  check every caller and every error path of each changed function.
- Error handling: errors swallowed, replaced by defaults, or reported as success;
  partial writes left behind after a failure; results that silently drop items.
- Authorization: every path that reads or changes protected data checks the caller,
  including new endpoints, batch paths, retries and admin or test hooks.
- Confidentiality: secrets, tokens, credentials or private data in logs, errors,
  public comments, URLs, test fixtures or responses; indirect disclosure through
  counts, timing, cursors or error differences.
- Input handling: untrusted input reaching paths, shells, queries, templates, parsers
  or size-sensitive buffers without validation or bounds.
- Tests: the changed behavior has a test that fails without the change; tests assert
  outcomes rather than implementation details.

Out of scope (owning lens):
- Concurrent callers, crash or restart mid-step, retries, replay, durability and
  resource bounds: `concurrency-restarts`.
- Whether the change does what its issue, specification and settled decisions require:
  `spec`.
- Simplicity, dead code, duplication and scope: `waste`.
- Document premise and readability: `design-spec`.

@rule house-rules:prompts/util/targeted-lens.md
@rule house-rules:prompts/util/review-procedure.md

### Inventories for correctness and security

1. **Failure table.** One row per failure the code or a dependency is shown to produce in the changed call chains,
   including resource acquisition and ownership transfer. Cite its producer: the call, documented dependency behaviour
   or observation. Columns: returned error, exception or unwinding, the cleanup that runs, the work a return skips,
   and what the caller sees. Include allocation or construction failures only with such evidence; a row for a returned
   error, or a guard that only resets a flag, does not cover a demonstrated exception or unwind.
   Trace each error's cause and category to the final caller-visible result, through every wrapper and
   serialization. Partial success never reports success. Trace sequential propagation yourself; the retry, replacement
   and recovery that follow a failure belong to the concurrency reviewer.
2. **Authorization table.** One row per entry point that reads or changes protected data. Columns: principal, action
   and resource, where the check is enforced, and every path that bypasses it (batch, retry, admin or test hooks).
3. **Published-value table.** One row per new or changed value per final consumer, for every value that reaches a
   log, comment, status, prompt, error, artifact or other output leaving the process, including generated headings,
   labels, embedded metadata and values passed whole; inside each, one row per interpolated expression or constructor
   field. A protected channel does not cover another channel the same value reaches. Serialization or escaping is not protection,
   and permission to publish paths or authored text does not cover credentials.
   Columns: origin and actual value kind, each transformation, the last protection applied, the final consumer, and
   whether any reachable input (not only the current fixtures) can carry a path, credential, raw diagnostic or private
   text. For a label on published content that claims completeness, identity or type, cite the condition that makes it
   true. Whether a status or diagnostic message's claims of cause, completion, exhaustion or recovery are true belongs
   to the specification reviewer; what such a message leaks stays in this table.
4. **Input-class table.** For each parser, encoder, selector, rewriter or consumer of a format in the change, one row
   per class: empty, one, several, repeated, maximum, whitespace, literal or fenced examples, quoted, nested and
   escaped contexts, tokens inside identifiers, and the mapping between parsed and source positions. When the format
   names repository objects or files, add their kinds (regular, link, directory, submodule, absent) and, when a name is
   resolved again later, one row per reachable change of kind (replacement, deletion, reuse). Compare with every other producer and consumer of the same format,
   including a second consumer that filters or selects by the same grammar: a prefilter, query or index that decides
   which records reach a parser must accept every form the parser accepts. When a recognizer can keep several matches,
   add rows for contained, partly overlapping, adjacent and repeated matches; the deciding line shows the ranges are
   disjoint before any replacement. When one pass selects a field or token, every later pass must use that selected
   value, not search again.
5. **Mode table.** One row per supported mode, backend, entry point, configured representation and optional
   combination, with wrappers and defaults expanded. For every fallback, wrapper, loader or interposer, one row per
   behavior of the native path it replaces (module identity and imports, each operation's argument count and type,
   including operations with no extra argument); "the caller sees an error" closes only the error case, not the case
   where the native path would have succeeded.
