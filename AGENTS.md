# RingFrame agent instructions

## Work locally

- Run these commands from the repository root:

  ```sh
  uv sync --locked
  uv run --locked pytest
  uv run --locked python -m ringframe --help
  uv build
  ```

- Put core changes in `core/ringframe/`, tests in `core/tests/`, and host
  instructions in `plugins/claude/` or `plugins/codex/`.
- Use disposable consumer workspaces for CLI examples and tests. Never create
  `.fab7/` in this source repository or commit ledgers, runs, plans, changelogs,
  dated notes, or task IDs.
- Preserve unrelated edits. Use the configured Git identity; never override
  `user.email`.

## Preserve contracts

- Put deterministic guarantees in the CLI and tests. Treat skill instructions
  as behavioral guidance, never as enforcement or proof of execution.
- Route every ledger write through the CLI. Keep finalized artifacts and
  ledger lines immutable; correct them with new records and typed links.
- Preserve public JSON keys, schemas, and exit codes from 0.0.1 onward. Extend
  contracts compatibly; do not silently remove or rename fields.
- Preserve global-option placement: `--json`, `--workspace`, `--actor`, and
  `--authority` may appear before or after subcommands.
- Keep hook scripts non-blocking and exiting 0, including on malformed input
  or a missing CLI. Record delivery only from the appropriate evidence.
- Mark source text verified only when it matches a captured Ask invocation
  in the resolved session; a session ID alone is insufficient.

## Implement and verify

- Add a failing regression test before changing behavior, then make the
  smallest change that passes it. Keep modules small and dependencies minimal.
- Run relevant deterministic tests and `git diff --check` before handoff;
  run the full suite for changes to shared contracts or skill instructions.
- Do not call a model from unit tests. Before sandboxed LLM testing or host
  acceptance claims, read and follow [LLM verification](LLM_VERIFICATION.md).
  Keep the authenticated test runner and its evidence outside the source tree.
- Cite retained qualification IDs and exact tested artifacts for host claims.
  Treat changed plugin bytes as needing fresh qualification; unit tests do
  not prove host or model behavior.

## Maintain documentation

- Keep the README focused on installation, first use, and material limitations.
- Keep technical documents short; link to the owning reference instead of
  repeating its contract. Use fenced `mermaid` blocks for every diagram or
  sequence; use tables for file layouts and vocabularies.
- Keep this file limited to instructions, guidance, and best practices. Put
  product descriptions and implementation details in `docs/`.
- Check commands, paths, event names, and claims against the current source.
  Separate implemented behavior, intended skill behavior, and tested evidence.
