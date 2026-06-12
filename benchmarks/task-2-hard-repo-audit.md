# Benchmark Task 2 — Whole-Repo Truth Audit & Repair (Hard / Long-Context)

**Context budget:** the repo's full text is ~450–500 KB ≈ **130–150k tokens**; the task
requires holding documentation AND implementation simultaneously while cross-referencing.
A single read pass already saturates a 200k window; the agentic conversation (re-reads,
search results, the model's own commits) pushes real demand to **400k–1M+**.
**What it measures:** long-context retention, cross-file reasoning at distance, judgment
(which side of a contradiction is authoritative), and sustained commit-by-commit execution.
**Expected outcome profile:** 131k/200k models (gpt-oss, Haiku, GLM, Kimi) can only do
lossy chunked passes — they should find local discrepancies but miss the **global** ones.
400k (Codex 5.3) should be mid-pack. 1M models (Fable 5, GPT-5.5, Opus 4.8, Qwen Max/Plus,
MiniMax M3*) can keep everything resident and should dominate the global tier.
(*MiniMax has the window but watch its precision — long context amplifies hallucination.)

---

## 1. Branch layout (anti-spoiler design)

Same squashed-baseline scheme as Task 1: `legacy/audit` is a **single commit** branched
from the FIRST commit of `master`, containing the full tree + scaffolding + seeded
discrepancies. Candidates see no history revealing what was edited.

```
master:          root ── c2 ── … ── tip
                   \
legacy/audit:      └── baseline   (one commit, seeds folded in)
                          \
legacy/audit-<model>:     └── model's own commits…
```

The candidate-facing problem lives on the branch at [`reports/TASK.md`](../reports/TASK.md).
The branch contains **no** `benchmarks/` folder and **no** prior model reports.

## 2. Operator setup

### 2.1 Scaffold (same recipe as Task 1 §2.1, branch name `legacy/audit`)

```bash
ROOT=$(git rev-list --max-parents=0 master)
git worktree add /tmp/bench-hard "$ROOT"
cd /tmp/bench-hard
git checkout -b legacy/audit
git checkout master -- .
rm -rf benchmarks reports && mkdir reports
# … add reports/TASK.md (see §3) …
git add -A && git commit -m "legacy: import"
```

### 2.2 Seed 15 discrepancies, then fold into the baseline

Plant the discrepancies from §2.3. The unit suite must still report **219 passed**.

```bash
poetry run pytest tests/ -q          # 219 passed required
git add -A && git commit --amend --no-edit
```

Answer key (tier, files involved, which side is wrong, one-line truth, intended repair)
goes **outside the repo**: `key/audit.md`.

### 2.3 Discrepancy menu

#### Tier L — Local (plant 5, weight ×1): claim and code in the same/adjacent file

1. `docker/README.md`: document the Java base image as `eclipse-temurin:17`
   (Dockerfile uses 21).
2. `plugins/go-1.20-dredd/README.md`: claim the parser "requires network access at
   runtime" (modules are pre-fetched precisely so it does not).
3. Docstring in `semverdredd/version.py`: claim integer scheme "preserves the patch
   number on minor bumps" (code resets it to 0).
4. `README.md` smoke section: document the runner flag as `--skip-build`
   (actual flag is `--no-build`).
5. `docs/schema.md`: document a snapshot field name that `snapshot/models.py` spells
   differently.

#### Tier C — Cross-file (plant 5, weight ×3): exactly 2 distant files

6. `HOWTO.md`: exit-code table says breaking changes exit `2`
   (truth: `EXIT_BREAKING_CHANGES_DETECTED = 10` in `cli/utils.py`).
7. `README.md` config section: claim env vars are LOWEST priority
   (`cli/config.py` merges them highest).
8. `INCLUDE-EXCLUDE-PROPOSAL.md` status table: mark "Multi-document priority chain"
   as ✅ Implemented (code still single-doc `yaml.safe_load`).
9. `snapshot/README.md`: misstate the `ChangeKind` ordering vs `snapshot/change_kind.py`.
10. `plans/improve-and-smoke-tests.md`: tick the DoD checkbox "CLI compare threads real
    versions" (CLI still hardcodes `"0.0.0"` in `cli/commands/compare.py`).

#### Tier G — Global (plant 5, weight ×6): 3+ far-apart files; the 1M discriminators

11. **Exit-code triangle:** change `tests/smoke/assert_demo.sh` expected code to `12`
    AND `HOWTO.md` to say `12`, while `cli/utils.py` defines `10` and `example/demo_*.sh`
    comments say `10`. Two sources agree on the wrong value — only a model holding all
    four decides which side is authoritative.
12. **Plugin-name chain:** in `plugins/python-3.10-dredd/pyproject.toml` rename the
    entry point to `python3` while `_BUILTIN_FALLBACK_SPECS`, `docker/Dockerfile.python`'s
    grep check, and `docker-compose.smoke.yml` all expect `python`.
13. **Fixture drift:** edit `tests/fixtures/go/v2_minor.yaml` to encode a breaking
    removal while `tests/test_cross_language.py` naming and
    `example/go/gogeometry2/geom.go` (the source it mirrors) stay additive.
    (Verify the suite still passes; weaken the edit if a test covers it.)
14. **Version-flow contradiction:** in `HOWTO.md`'s walkthrough show `bump` producing a
    date-scheme patch while the walkthrough's own `.semver.yaml` snippet sets
    `patch_scheme: integer`; `README.md`'s scheme table stays correct.
15. **Three-way option rename:** in `example/demo_java.sh` use a nonexistent `--options`
    flag and reference it in `plugins/java-1.8-dredd/README.md`; the real mechanism is
    config-driven `snapshot_options` (parser truth in `cli/__init__.py`).

### 2.4 Per-model run

```bash
git branch legacy/audit-<model> legacy/audit
```

Fresh workspace/conversation on that branch; the only user message:

> Read `reports/TASK.md` and complete the task it describes.

No follow-ups, identical settings for all. If a model dies on context overflow, collect
whatever it committed — that IS the result. Record billed $, tokens, wall time.

## 3. Candidate-facing problem — content of `reports/TASK.md` on the branch

```markdown
# TASK — Repository Truth Audit & Repair

This repository's documentation (`README.md`, `HOWTO.md`, `docs/`, `snapshot/README.md`,
plugin READMEs, `docker/README.md`, `INCLUDE-EXCLUDE-PROPOSAL.md`, `plans/`) makes many
claims about the code's behavior. A number of contradictions have been planted between
claim and reality — anywhere in the repo. In some, the documentation lies; in others,
the code/script/fixture/Dockerfile/workflow is what's wrong and the docs are right.

Your job:

1. Audit the WHOLE repository and find every claim-vs-reality contradiction.
2. For each one, decide which side is authoritative, and FIX the wrong side —
   **one git commit per contradiction**, message format:
   `fix: <short summary> (<wrong file>)`
   Plan your own approach; order, navigation, and method are up to you.
3. Write `reports/report.md` and commit it last (`docs: benchmark report`):

   | # | commit | claim location(s) | code location(s) | contradiction | wrong side | fix applied |
      |---|--------|-------------------|------------------|---------------|------------|-------------|

Rules:

- The unit test suite passes BEFORE your changes and must still pass (219) AFTER.
- "X and Y disagree" without picking the wrong side earns at most half credit.
- Report only real contradictions — not style, not "docs could be clearer."
  False reports are penalized.
- Do not rewrite history.
```

## 4. Collection — named stash per model

```bash
bash scripts/bench/stash-from-branch.sh legacy/audit legacy/audit-<model> <model-name>
```

`git stash list` on `legacy/audit` becomes the grading inbox: each named stash holds the
model's full diff (repairs + `reports/report.md`).

## 5. Grading — agent procedure

Run a grader agent on `legacy/audit` with the answer key pasted into its prompt
(the key never enters the repo):

> For each stash in `git stash list`:
> 1. `git checkout legacy/audit && git checkout -- . && git clean -fd`
> 2. `git stash apply "stash^{/<name>}"`; read `reports/report.md`; inspect `git diff`.
> 3. For each of the 15 key entries classify:
     > **found + correct side + fixed** / **found + wrong side picked** /
     > **found, not fixed** / **missed**.
     > G-tier credit additionally requires the report to name the authoritative file
     > AND at least one wrong file.
> 4. False positives: report rows or diff hunks matching no key entry. Genuine unseeded
     > discrepancies the model proves are NOT false positives — verify manually and score
     > as tier C (add them to the key for later runs).
> 5. Run `poetry run pytest tests/ -q` after applying — must pass.
> 6. Output one scorecard per model plus a ranking by Score and by Value.

### Scoring formula

```
per item:   found + correct side + fixed = full tier weight (L 1, C 3, G 6)
            found + fixed but wrong-side verdict = half weight
            found in report, not fixed = half weight
penalties:  false positive = −2;  suite broken = −6;  no report.md = −5
max Score = 5×1 + 5×3 + 5×6 = 50
Value = Score / billed_$
```

## 6. Expected outcome profile

| Window   | Models                                                | Expectation                                                       |
|----------|-------------------------------------------------------|-------------------------------------------------------------------|
| 131–202k | gpt-oss, Haiku, GLM                                   | L mostly; C partial; G ≈ 0. May overflow mid-run.                 |
| 262k     | Kimi K2.6                                             | L + most C; 1–2 G at best                                         |
| 400k     | GPT-5.3-Codex                                         | L + C; partial G (2–3)                                            |
| 1M+      | Fable 5, GPT-5.5, Opus 4.8, Qwen Max/Plus, MiniMax M3 | Sweep L+C, 3–5 G; differences here are the real capability signal |

Key comparisons to extract:

- **G-tier recall vs. window size** — the isolated long-context payoff.
- **Precision under long context** — hallucination rate after 300k+ tokens of reading
  (watch MiniMax and Qwen Plus specifically).
- **Verdict quality** — wrong-side picks reveal shallow pattern-matching even when the
  contradiction itself was spotted.
- **Value** — whether 1M-window premium pricing buys proportional G-tier results; Qwen
  Max/Plus and MiniMax offer 1M windows at a fraction of Anthropic/OpenAI prices and are
  the value-side stress test of this benchmark.
