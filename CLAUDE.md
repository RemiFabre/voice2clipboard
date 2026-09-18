# voice2clipboard — notes for agents working in this repository

This repository is **public**. Its owner's dictations are private, often internal company
communication, even when they look like test material.

- Never commit a transcript, an adjudicated reference, or a sentence-level error listing of the
  owner's speech. Those live under `recordings/` or `benchmarks/private/`, both gitignored, and
  tracked files may only point to them by path.
- Research notes and benchmark reports may carry aggregate numbers (WER, timings, counts,
  chunk sizes) and generic or synthetic examples, never quoted dictated sentences.
- The pre-commit hook in `scripts/git-hooks/` enforces the obvious cases; install it with
  `git config core.hooksPath scripts/git-hooks` and do not bypass it.
- Hard-coded home paths and device identifiers are accepted here by the owner's decision: this
  is an "adapt it for yourself" setup, not a library.
