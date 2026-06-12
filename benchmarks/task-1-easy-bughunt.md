# Benchmark Task 1 — Seeded Bug Hunt & Fix (Easy / Baseline)

**Context budget:** fits in 100–200k tokens end-to-end. Every model in the roster can run it.
**What it measures:** correctness (precision), deep reading (weighted recall), execution
discipline (commit-by-commit work), and cost discipline.
**Expected outcome profile:** small models (gpt-oss-120b, MiniMax M3, Qwen Plus, GLM, Haiku)
should be able to complete it; big models (Fable 5, GPT-5.5, Opus 4.8) are expected to be
**overkill** here — they should not score meaningfully higher, so their `Score/$` will look
bad. That is the point: this task establishes the floor and exposes overpaying.

---

## 1. Branch layout (anti-spoiler design)

All benchmark branches use a **squashed single-commit baseline** branched from the FIRST
commit of `master`. The seeded defects are folded into that one commit, so candidates see
no history that reveals what was changed:

```
master:          root ── c2 ── c3 ── … ── tip
                   \
legacy/bughunting:      └── baseline   (one commit: full tree + scaffolding + SEEDED defects)
                          \
legacy/bughunting-<model>:     └── model's own commits…
```

This also makes collection trivial: a model's entire contribution is
`git diff legacy/bughunting legacy/bughunting-<model>`.

The candidate-facing problem statement lives **on the branch** at
[`reports/TASK.md`](../reports/TASK.md) — the model is pointed at that file and nothing else.
The branch contains **no** `benchmarks/` folder and **no** prior model reports.

## 2. Operator setup

### 2.1 Create the scaffold branch (already automated — see §2.4)

```bash
ROOT=$(git rev-list --max-parents=0 master)
git worktree add /tmp/bench-easy "$ROOT"
cd /tmp/bench-easy
git checkout -b legacy/bughunting
git checkout master -- .                 # bring in the full current tree
rm -rf benchmarks reports                # strip benchmark secrets + old reports
mkdir reports                            # TASK.md goes here (see §3)
# … add reports/TASK.md …
git add -A
git commit -m "legacy: import"
```

### 2.2 Seed the defects (operator-only, then squash into baseline)

Plant **10 defects** from the menu in §2.3. Every defect MUST be in a code path **not
covered by the unit test suite** — after seeding, `poetry run pytest tests/ -q` must still
report **219 passed**. This kills the "run pytest, see green, declare victory" shortcut.

Then **fold the seeds into the baseline commit** so no diff is visible in history:

```bash
# on legacy/bughunting, after editing the files:
poetry run pytest tests/ -q              # must be 219 passed
git add -A
git commit --amend --no-edit             # seeds disappear into the baseline commit
```

Write the answer key (file, line, description, intended fix) **outside the repo**,
e.g. `key/bughunting.md`. It must not be readable by candidates.

### 2.3 Defect menu (pick 10; vary between runs)

Scoped file set (~25–30k tokens total reading):

| File                            | Tier                       |
|---------------------------------|----------------------------|
| `tests/smoke/assert_demo.sh`    | Easy                       |
| `scripts/smoke.sh`              | Easy                       |
| `.github/workflows/smoke.yml`   | Medium                     |
| `cli/commands/compare.py`       | Medium                     |
| `cli/config.py`                 | Medium                     |
| `cli/commands/plugin.py`        | Hard                       |
| `semverdredd/plugin_manager.py` | Hard                       |
| `docker/Dockerfile.java`        | Hard                       |
| `semverdredd/version.py`        | **TRAP — leave untouched** |
| `docker/README.md`              | **TRAP — leave untouched** |

**Easy (plant 3, weight ×1):**

1. `assert_demo.sh`: swap the expected strings — geometry1→2 asserts `BREAKING`,
   geometry2→1 asserts `MINOR`.
2. `assert_demo.sh`: change the expected breaking-change exit code from `10` to `1`
   (truth: `EXIT_BREAKING_CHANGES_DETECTED = 10` in `cli/utils.py`).
3. `scripts/smoke.sh`: on the build-failure branch, forget to set the `FAILED` flag,
   so a failed build still exits 0.

**Medium (plant 4, weight ×2):**

4. `cli/commands/compare.py`: pass `extra_options=snapshot_options` only to the OLD
   snapshot call, drop it from the NEW one (silent asymmetric scoping).
5. `cli/config.py`: make the invalid-`patch_scheme` fallback silent (or send the warning
   to stdout) — verify the warning branch isn't covered by a test first.
6. `.github/workflows/smoke.yml`: delete the `BUILDX_BAKE_GITHUB_ACTIONS_CACHE: "true"`
   env line but keep the comment "Docker layer caching keeps repeat runs reasonable".
7. `cli/config.py`: in `snapshot_options()`, emit the `include` key even when the list is
   empty (breaks the documented "absent keys when unset" backward-compat contract).

**Hard (plant 3, weight ×4):**

8. `semverdredd/plugin_manager.py`: flip discovery precedence — builtin fallback wins
   over entry points.
9. `cli/commands/plugin.py`: in manifest-based removal, make the eviction set-logic also
   evict a sibling plugin's manifest entry.
10. `docker/Dockerfile.java`: change the build sanity check
    `grep -q java` → `grep -q dredd` (matches ANY plugin — check becomes vacuous).

### 2.4 Per-model run

For each model, give it a private copy of the baseline branch:

```bash
git branch legacy/bughunting-<model> legacy/bughunting
```

Open a **fresh workspace/conversation** on that branch and send only this user message:

> Read `reports/TASK.md` and complete the task it describes.

No follow-ups. Same mode/settings for everyone. Record billed $, tokens, wall time.

## 3. Candidate-facing problem — content of `reports/TASK.md` on the branch

```markdown
# TASK — Defect Hunt & Fix

This repository contains a number of intentionally planted functional defects
(wrong behavior, broken contracts, vacuous checks). Your job:

1. Find them. They are confined to these files:
   `tests/smoke/assert_demo.sh`, `scripts/smoke.sh`, `.github/workflows/smoke.yml`,
   `cli/commands/compare.py`, `cli/config.py`, `cli/commands/plugin.py`,
   `semverdredd/plugin_manager.py`, `docker/Dockerfile.java`,
   `semverdredd/version.py`, `docker/README.md`.
   Some of these files may contain ZERO defects.
   You may read any other file in the repo as reference for intended behavior
   (`README.md`, `docs/`, `HOWTO.md`, tests).

2. Fix them — **one git commit per defect**, message format:
   `fix: <short defect summary> (<file>)`
   Plan your own approach; order and method are up to you.

3. Write `reports/report.md` and commit it last (`docs: benchmark report`):

   | # | commit | file:line | defect | why it is wrong | fix applied |
      |---|--------|-----------|--------|-----------------|-------------|

Rules:

- The unit test suite passes BEFORE your changes — green tests are NOT evidence of
  correctness; the defects live outside test coverage. The suite must still pass
  (219 passed) AFTER your fixes.
- Report only functional defects, not style. False reports are penalized.
- Do not rewrite history; do not touch files outside your fixes + the report.
```

## 4. Collection — named stash per model

After each model finishes (working tree clean, everything committed):

```bash
bash scripts/bench/stash-from-branch.sh legacy/bughunting legacy/bughunting-<model> <model-name>
```

This produces a named stash on the baseline containing the model's full diff
(fixes + `reports/report.md`). Repeat per model; `git stash list` becomes the inbox
for grading.

## 5. Grading — agent procedure

Run a grader agent (any strong model) on the baseline branch with the answer key
(paste key contents into the grader prompt; the key never enters the repo):

> You are grading benchmark runs. The answer key (10 seeded defects) is below: …
>
> For each stash in `git stash list`:
> 1. `git checkout legacy/bughunting && git checkout -- . && git clean -fd`
> 2. `git stash apply "stash^{/<name>}"`
> 3. Read `reports/report.md`; diff the work (`git diff`).
> 4. For each key entry decide: **found+fixed** (reported AND the diff corrects the
     > behavior) / **found only** / **fixed only** (silent fix, not in report) / **missed**.
> 5. Count false positives: report rows or diff hunks not matching any key entry
     > (trap-file claims are automatic false positives).
> 6. Verify `poetry run pytest tests/ -q` still passes after applying.
> 7. Note commit hygiene from the report's commit column (one fix per commit?).
     > Output one scorecard table per model plus a final ranking by Score and by Value.

### Scoring formula

```
per defect:  found+fixed = full tier weight (easy 1, medium 2, hard 4)
             found only OR fixed only = half weight
penalties:   false positive = −2;  test suite broken = −5;  no report.md = −3
max Score = 3×1 + 4×2 + 3×4 = 23
Value = Score / billed_$        (floor billed_$ at $0.05)
```

## 6. Expected cost envelope

| Model class                         | Expected billed cost | Expected Score |
|-------------------------------------|----------------------|----------------|
| gpt-oss-120b, MiniMax M3, Qwen Plus | $0.02–0.25           | 6–14           |
| GLM 5.1, Haiku 4.5, Kimi K2.6       | $0.10–0.60           | 10–18          |
| Sonnet 4.6, Codex 5.3, Qwen Max     | $0.40–2.00           | 14–21          |
| Opus 4.8, GPT-5.5, Fable 5          | $2.00–8.00           | 16–23          |

If a big model bills >$8 here, that is a negative signal regardless of Score — the task
is solvable in ~60k tokens of reading plus ten small edits.
