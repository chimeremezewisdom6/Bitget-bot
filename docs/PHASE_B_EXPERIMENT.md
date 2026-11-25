# Phase B experiment contract

This document freezes the Phase B definitions that are not obvious from the code. The machine-readable source of truth is `research/specs/phase_b_v2.json`; `phase_b_v1.json` is retained for reproducibility. The registry is frozen and hash-checked at evaluation time.

## Scope and safety

- Research only. No order submission, amendment or cancellation; no leverage, margin, position, transfer or withdrawal calls.
- The collector uses public Bitget USDT-FUTURES market data only. It does not use Bitget API keys.
- The scheduled collector is disabled until the repository variable `PHASE_B_COLLECTOR_ENABLED` is set to `true`. Manual `workflow_dispatch` also requires that variable; there is no `--force` bypass.
- Evaluation is deterministic Python. It does not call Pollinations or any other LLM.
- Evaluation reports are GitHub Actions artifacts. The only write is the append-only holdout ledger on the protected `holdout-ledger` branch; nothing is written to `main`.

## Timestamps and bars

- All timestamps are UTC milliseconds.
- A feature `ts_ms` is the collection time of the 5-minute cycle.
- A candle `ts` is the candle open time. Only fully closed 1-minute candles are used.
- Entry is the open of the first 1-minute candle whose open time is strictly after the event `ts_ms` (`entry_latency_bars=1`).
- Exit is the close of the candle at `entry_index + horizon_min - 1`, which is exactly `horizon_min` minutes after the entry open.
- No future candle is used to detect an event.

## Return definitions

- 1-minute return: `100 * (close_t / close_{t-1} - 1)`.
- 5-, 15- and 60-minute returns: `100 * (close_t / close_{t-n} - 1)` using the last fully closed candle.
- Forward return: `100 * (exit_price / entry_price - 1)`, signed by the event direction.
- Spot 5-minute return uses spot 1-minute candles with the same formula.

## Z-score baselines

- Turnover z: `(current_1m_quote_turnover - mean(previous 60 fully closed 1m quote turnovers)) / stdev(previous 60)`. The current candle is the last closed candle and is excluded from the baseline. If the baseline standard deviation is zero or fewer than 61 candles exist, no z-score is produced.
- Spot turnover z: the same calculation on the spot 1-minute quote turnover series.
- Breakout z: the turnover z at the breakout bar, using the 60 bars before that bar. The breakout bar is the first of the three confirmation bars.
- A z-score is never computed from a future bar and is never carried across a detected gap.

## Volatility flag

The approved rule is unchanged:

- Use 61 fully closed 1-minute candles, covering 60 close-to-close intervals.
- Compute every close-to-close percentage change.
- `flag_0_7 = max(abs(change)) >= 0.7`.
- A missing interval produces `volatility_status="GAP"` and no flag.
- Fewer than 61 candles produces `volatility_status="INSUFFICIENT_CANDLES"` and no flag.
- The flag is a reported bucket, not a filter that deletes events. `flag_true`, `flag_false`, `flag_gap` and `flag_insufficient` are reported separately.

## Event directions

| Event | Direction |
|---|---|
| `taker_aggression` | Sign of taker imbalance; `ADEQUATE` quality required. ADEQUATE means at least 50 fills, at least 60 seconds of fill span, newest fill no older than 60 seconds, and a non-empty sample. Coverage is diagnostic only. |
| `turnover_expansion` | Sign of the 1-minute return |
| `oi_change` | Positive OI growth of at least 2.0% with an absolute 15-minute price move of at least 0.2%. Direction is the price return; OI direction and alignment are recorded separately. Negative OI is diagnostic only and is not an event. |
| `liquidation_spike` | `fade` = fade the forced flow (long liquidations → LONG, short liquidations → SHORT); `follow` = follow the forced flow (long liquidations → SHORT, short liquidations → LONG) |
| `spot_lead` | Sign of the spot 5-minute return. Leadership is timestamp-based: the first spot 0.2% crossing must precede the perpetual crossing, or the perpetual must not have crossed yet. Return magnitude is not compared. |
| `absorption` | Fade the aggressor: buying imbalance → SHORT; selling imbalance → LONG |
| `breakout` | Breakout direction; requires a present turnover z of at least 2.0 and excludes failed breakouts |
| `failed_breakout` | Fade the failed breakout direction; requires a present turnover z of at least 2.0 |

Negative OI moves are written to `oi_negative.jsonl` with `oi_negative_summary.json`; they are descriptive diagnostics and are never scored as an event.

## Horizons

All specs use 5, 15, 30 and 60 minutes. The same detected events are scored at each horizon; the sample size is not divided by the number of horizons.

## Cooldown and event-reset rules

1. Detection runs on the 5-minute feature grid.
2. Dedupe: keep the earliest event per symbol/event type/direction within 60 minutes. This is the detection cooldown.
3. Non-overlap: for each symbol, spec and horizon, accept an event only if its entry timestamp is greater than or equal to the previous accepted event's exit timestamp.
4. An event rejected for overlap does not reset the cooldown or the last exit. It is counted as `skipped_overlap`.
5. An event with insufficient forward candles is counted as `skipped_no_forward` and does not update the last exit.
6. The first accepted event for a symbol/spec/horizon has no prior exit constraint.
7. The holdout uses the same rules; it is not evaluated while locked.

## Costs

- Fee: per-symbol `takerFeeRate` from public instrument metadata, converted to basis points per side. Both sides are charged. The observed existing metadata is 6.0 bps per side. The collector records `fee_status=PROVIDED` when public metadata exists and `fee_status=FEE_ESTIMATED` when it is absent; the evaluator then uses the frozen 6.0 bps fallback and carries `FEE_ESTIMATED` into the scored result.
- Spread: `spread_bps` is the full bid-ask spread, calculated as `(ask - bid) / mid * 10_000`. It is charged once per round trip: entering at the ask and exiting at the bid gives up one full spread. Do not double-charge it. If missing, the event is excluded from net results and counted as `SPREAD_MISSING`; no spread is invented.
- Slippage: 5 bps total in the headline. Sensitivity results at 0, 2, 5 and 10 bps are part of the frozen defaults and may be reported separately.
- Funding: actual ticker `fundingRate`, prorated by `horizon_min / 480`, sign-adjusted for the event direction. A positive funding rate is a cost for longs and a credit for shorts. If funding is missing, `net_bps` is not fabricated; `net_ex_funding_bps` is reported and the result is marked `FUNDING_MISSING`.
- No cost is silently set to zero.

## Splits and holdout

- Three-day pilot: train = oldest day, validation = middle day, holdout = newest day, with minimum days 1/1/1. The holdout is locked and is not evaluated or described statistically.
- At 30 complete days: 18 train / 6 validation / 6 holdout, with minimum validation and holdout days of 6 each. The profile is `standard_30d`; the policy name is `locked_last_20pct`.
- A 60-minute embargo applies at internal boundaries. Events whose forward horizon crosses a boundary are excluded. Events in the first 64 minutes of validation or test are also excluded because their trailing feature lookback would cross the prior split.
- The holdout requires all of the following: at least 30 complete days, manual `confirm_holdout=true`, the exact frozen registry hash, an authorized `holdout_unlock_at` date not in the future (UTC), and an available protected ledger. The nightly schedule supplies none of these.
- The holdout is never used to select thresholds or specs. Any spec change creates a new frozen version and hash.
- The holdout ledger is an append-only, versioned JSON record on the protected `holdout-ledger` branch. It is written only after an authorized evaluation completes successfully. Repeated evaluation of the same frozen hash is refused when the ledger already contains that hash. The ledger job is separate from the read-only evaluation job, requires the `phase-b-holdout` environment, and never writes `main`.
- Ledger schema version 2 contains `evaluated_hashes` plus an append-only `audit` list. Events are `attempted`, `completed`, and `results_inspected`. `completed` is written only when the hash is actually consumed; an open or abandoned PR is not a completed evaluation. `results_inspected` is never written by a merge or any PR automation; a reviewer records it explicitly with `python -m research.nightly --record-audit ledger/holdout_ledger.json --audit-event results_inspected --holdout-hash <hash> --audit-actor <reviewer>`.
- The workflow refuses to start a holdout while an open pull request targets `holdout-ledger`. That prevents a second evaluation while a prior ledger-update PR is awaiting human merge.
- Any closed unmerged PR on `holdout-ledger`, including a legacy PR with no experiment hash, is detected as an abandoned attempt. It does not consume the hash and does not become a completed evaluation. Retrying requires a manual `workflow_dispatch` with `retry_authorization` set to the exact frozen registry hash and approval by the required `phase-b-holdout` reviewers. Without both, the workflow fails closed. A closed merged PR whose hash is missing from the ledger, or whose body has no hash at all, also fails closed and requires manual ledger audit.
- The workflow also requires the repository variable `PHASE_B_HOLDOUT_ENVIRONMENT_READY=true`. Set it only after `phase-b-holdout` exists with the required reviewers. If the variable is absent, holdout jobs do not run. The variable alone is not sufficient: `prepare-ledger` and `record-ledger` run under the actual `phase-b-holdout` environment, call the GitHub environment API, and fail if the environment is missing, lacks required reviewers, permits self-review, or permits administrator bypass.
- A holdout is complete only when every overall spec/horizon result is powered. Bucket results remain diagnostic; a sparse bucket does not permanently block an otherwise valid overall holdout. `insufficient_overall_holdout_rows` gates recording; `insufficient_bucket_holdout_rows` is reported separately.
- Ledger updates use one of two modes. `HOLDOUT_LEDGER_MODE=app` uses a dedicated GitHub App with only Contents write, allowlisted by the ledger ruleset, and falls back to a pull request if the direct push is rejected. Otherwise the job opens a pull request for human review and merge. Do not add `github-actions[bot]` to a broad branch-protection bypass list.
- Production holdout execution is restricted to Linux CI. The workflow uses `--require-linux-ci`; local Windows execution is not an authorized holdout path.
- One-time setup must follow the exact checklist below. The readiness variable is only an attestation; the workflow also calls the GitHub environment API and rejects a missing, unprotected, self-reviewable, or administrator-bypassable `phase-b-holdout` environment.

## Workflow action pinning

- Every `uses: actions/...` reference is pinned to a 40-character commit SHA. The version is kept as a trailing comment for review.
- Review pins monthly and before any Phase B release. Compare the current tag with the pinned SHA using `git ls-remote --tags`, read the upstream release notes, and check for breaking changes or security advisories.
- Update pins in one small change, keep the version comment, run the full test suite, and review the diff. Do not auto-merge pin updates without a human review.
- A Dependabot or Renovate pull request may propose updates, but it follows the same review and test process. No workflow may use a floating tag such as `@v4` or `@main`.

## Manual GitHub setup checklist

Do these in order. Do not set `PHASE_B_HOLDOUT_ENVIRONMENT_READY=true` until steps 1-4 are verified.

### 1. Holdout branch

1. Create `holdout-ledger` from `main`.
2. Add only `holdout_ledger.json` with:
   ```json
   {"schema_version": 2, "evaluated_hashes": [], "audit": []}
   ```
3. Commit and push the branch. Do not put reports, code, or secrets on it.
4. Confirm the branch is readable by Actions and writable only through the approved path.

### 2. Branch ruleset

Create a branch ruleset with these exact values:

| Setting | Required value |
|---|---|
| Name | `phase-b-holdout-ledger` |
| Enforcement | Active |
| Target branches | Include `refs/heads/holdout-ledger` only |
| Bypass list | Only the dedicated `holdout-ledger` GitHub App, if app mode is used |
| Repository admin bypass | **Disabled** |
| Team bypass | **Disabled** |
| `github-actions[bot]` bypass | **Never added** |
| Restrict deletions | Enabled |
| Block force pushes | Enabled |
| Require a pull request before merging | Enabled |
| Required approvals | At least 1 |
| Dismiss stale approvals | Enabled |
| Require conversation resolution | Enabled |
| Require status checks | Leave empty unless a separate required check is registered |

The app may have only `Contents: write`. It must be installed on this repository and named in the ruleset bypass list. It must not have `Administration: write`, `Environments: write`, or organization-wide access. If an app-specific bypass is unavailable in this repository, do **not** weaken the ruleset: set `HOLDOUT_LEDGER_MODE=pr` and use the pull-request path instead.

### 3. Protected environment

1. Create environment `phase-b-holdout` exactly.
2. Add at least two trusted reviewers or one trusted team with at least two members.
3. Enable **Prevent self-review**.
4. Disable **Allow administrators to bypass**.
5. Restrict deployment branches to `main`.
6. Do not add environment secrets for trading or exchange access.
7. The workflow validates the API response. A valid response must show:
   - `name = phase-b-holdout`
   - a `required_reviewers` protection rule
   - a non-empty reviewer list
   - `prevent_self_review = true`
   - `can_admins_bypass = false`

### 4. Reviewers

- Use at least two humans who are independent of the holdout author.
- Do not use a bot, the workflow actor, or the app as a reviewer.
- Record the reviewer names in the repository's research operations record.

### 5. Repository variables and secrets

Repository variables:

- `PHASE_B_HOLDOUT_ENVIRONMENT_READY=true` only after steps 1-4 pass.
- `HOLDOUT_LEDGER_MODE=app` or `HOLDOUT_LEDGER_MODE=pr`.
- `HOLDOUT_LEDGER_APP_ID=<app id>` only in app mode.

Secrets:

- `HOLDOUT_LEDGER_APP_PRIVATE_KEY` only in app mode.
- `HOLDOUT_ENVIRONMENT_READ_TOKEN` is a read-only token used only to inspect `phase-b-holdout`. It needs repository Administration read or Environments read. Store it as a repository secret. If it is absent, the workflow tries `GITHUB_TOKEN`; if that token cannot read the environment, the holdout fails closed.
- Do not add exchange API keys, trading keys, or withdrawal permissions.

### 6. Verification

1. Run:
   ```bash
   gh api repos/<owner>/<repo>/environments/phase-b-holdout > environment.json
   python -m research.nightly --verify-holdout-environment --environment-json environment.json
   ```
   It must print `phase-b-holdout protection verified`.
2. Confirm the ruleset shows only the intended app bypass and no admin bypass.
3. Confirm `holdout_ledger.json` has schema 2 and an empty `audit` list.
4. Confirm the holdout workflow is dispatched manually, never by schedule.
5. Confirm the workflow is running on Linux CI.

### 7. Retrying after an abandoned PR

A closed unmerged ledger PR, including a legacy PR with no experiment hash, blocks the next holdout. To retry:

1. Open a manual `workflow_dispatch` of `evaluate-phase-b.yml`.
2. Set `retry_authorization` to the exact frozen registry hash.
3. Obtain approval from the required `phase-b-holdout` reviewers.
4. Keep `PHASE_B_HOLDOUT_ENVIRONMENT_READY=true` only while the environment and ruleset remain correct.

There is no schedule, label, comment, or automatic retry path that bypasses these steps.

## Multiple testing

- Primary family: all primary specs, including both liquidation hypotheses, corrected together with Benjamini-Hochberg FDR at q = 0.10.
- Secondary family: the separately registered strict absorption hypothesis, corrected in its own family at q = 0.10.
- Every reported test, including overall and bucket tests, is part of its family's correction.
- Raw p-values, q-values, rejected flags, total tests and expected false discoveries are reported.

## Sample-size rules

- Minimum observations: 30 pipeline, 100 validation, 200 holdout.
- Minimum days: 1 pipeline, 6 validation, 6 holdout for the standard 30-day profile; 1/1/1 for the three-day pilot.
- If either minimum is not met, the verdict is `INSUFFICIENT_SAMPLE`. Thresholds are never weakened to reach a sample size.
- A `VALIDATED` verdict requires q ≤ 0.10, a bootstrap 95% confidence interval whose lower bound is above zero, and both sample minimums.
- Directional accuracy alone is not a profitability claim. Results are reported with effect size, confidence interval, adverse movement, duration and costs.

## Data-quality labels

`NO_DATA`, `MISSING`, `GAP`, `STALE`, `INCOMPLETE`, `TRUNCATED`, `DEGRADED`, `DELAYED`, `INSUFFICIENT_SAMPLE`.

The evaluator and watchdog never synthesize candles, fills, liquidations or order-book rows. Zeros from the global liquidation page are marked `PARTIAL_PAGE`; they are not treated as proof that no liquidation occurred.

## Data sources

- Perpetual candles, tickers, instruments, order book, fills, open interest, funding and liquidations: Bitget USDT-FUTURES public market endpoints.
- Spot basis and spot lead: Bitget spot market endpoints, mapped only where an exact spot symbol exists.
- Every bundle records `data_source`, `slot`, `git_sha`, `started_ms`, `finished_ms`, `outcome`, symbol counts and `trading_enabled=false`.
