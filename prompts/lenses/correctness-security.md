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
