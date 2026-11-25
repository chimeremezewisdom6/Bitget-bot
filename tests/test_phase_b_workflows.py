import unittest
from pathlib import Path


class PhaseBWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def read(self, name):
        return (self.root / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_collector_is_guarded_and_read_only(self):
        text = self.read("collect-phase-b.yml")
        self.assertIn("PHASE_B_COLLECTOR_ENABLED", text)
        self.assertIn('cron: "1-59/5 * * * *"', text)
        self.assertIn("contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("actions: write", text)
        self.assertNotIn("pull_request_target", text)
        self.assertNotIn("secrets: inherit", text)
        self.assertIn("python -m collector.cli", text)
        self.assertIn("retention-days: 4", text)
        self.assertIn("if: vars.PHASE_B_COLLECTOR_ENABLED == 'true'", text)
        self.assertNotIn("github.event_name == 'workflow_dispatch'", text)

    def test_nightly_is_read_only_and_uses_frozen_specs(self):
        text = self.read("evaluate-phase-b.yml")
        self.assertIn('cron: "15 2 * * *"', text)
        self.assertIn("contents: read", text)
        self.assertIn("actions: read", text)
        self.assertIn("python -m research.nightly", text)
        self.assertIn("--fdr-q 0.10", text)
        self.assertIn("--min-n 30", text)
        self.assertIn("research-report-", text)
        evaluation, ledger = text.split("  record-ledger:", 1)
        self.assertNotIn("contents: write", evaluation)
        self.assertIn("contents: write", ledger)
        self.assertIn("ref: holdout-ledger", ledger)
        self.assertIn("environment: phase-b-holdout", ledger)
        self.assertIn("git push origin HEAD:holdout-ledger", ledger)
        self.assertNotIn("git push origin main", ledger)
        self.assertIn("phase-b-holdout-ledger", text)
        self.assertIn("--holdout-ledger", text)
        self.assertIn("--record-holdout", ledger)
        self.assertIn("create-github-app-token", ledger)
        self.assertIn("permission-contents: write", ledger)
        self.assertIn("HOLDOUT_LEDGER_MODE", ledger)
        self.assertIn("pull-requests: write", ledger)
        self.assertIn("needs.evaluate.result == 'success'", ledger)
        self.assertIn("holdout-result", ledger)
        self.assertIn("registry_hash", text)
        self.assertNotIn("github-actions[bot]", ledger)
        self.assertIn("preflight", text)
        self.assertIn("Verify frozen registry hash before any data download", text)
        self.assertIn("--preflight-holdout", text)
        self.assertIn("check-pending", text)
        self.assertIn("gh pr list", text)
        self.assertIn("--base holdout-ledger", text)
        self.assertIn("--state closed", text)
        self.assertIn("mergedAt", text)
        self.assertIn("--check-holdout-prs", text)
        self.assertIn("--holdout-ledger", text)
        self.assertIn("retry_authorization", text)
        self.assertIn("pull-requests: read", text)
        self.assertIn("needs.check-pending.result == 'success'", text)
        self.assertIn(
            "inputs.confirm_holdout != 'true' && needs.prepare-ledger.result == 'skipped'",
            text,
        )
        self.assertNotIn(
            "(needs.prepare-ledger.result == 'success' || needs.prepare-ledger.result == 'skipped')",
            text,
        )
        self.assertIn("vars.PHASE_B_HOLDOUT_ENVIRONMENT_READY == 'true'", text)
        self.assertIn("phase-b-holdout is not attested ready", text)
        self.assertIn("--verify-holdout-environment", text)
        self.assertIn("HOLDOUT_ENVIRONMENT_READ_TOKEN", text)
        self.assertIn("gh api", text)
        self.assertGreaterEqual(text.count("environment: phase-b-holdout"), 2)
        self.assertIn("--verify-holdout-state", text)
        self.assertIn("--verify-holdout-result", text)
        self.assertIn("--require-linux-ci", text)
        self.assertIn("set -euo pipefail", text)
        self.assertIn("vars.HOLDOUT_LEDGER_MODE != 'app' || steps.ledger-token.outcome != 'success' || steps.ledger-push.outcome == 'failure'", ledger)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", text)
        self.assertIn("actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349", text)
        self.assertNotIn("uses: actions/checkout@v4", text)

    def test_phase_b_collector_has_no_authenticated_fee_lookup(self):
        for path in (
            self.root / "collector" / "cli.py",
            self.root / "collector" / "cycle.py",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("bitget_auth", source)
            self.assertNotIn("/api/v3/account", source)
            self.assertNotIn("ACCESS-KEY", source)
        workflow = (self.root / ".github/workflows/collect-phase-b.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("BITGET_API", workflow)
        self.assertNotIn("BITGET_SECRET", workflow)

    def test_phase_b_actions_are_sha_pinned(self):
        for name in ("collect-phase-b.yml", "evaluate-phase-b.yml", "watchdog-phase-b.yml"):
            path = self.root / ".github" / "workflows" / name
            for line in path.read_text(encoding="utf-8").splitlines():
                if "uses: actions/" in line:
                    self.assertRegex(
                        line,
                        r"uses: actions/[^@]+@[0-9a-f]{40}(\s|$)",
                        f"unpinned action in {path.name}: {line.strip()}",
                    )

    def test_watchdog_is_read_only(self):
        text = self.read("watchdog-phase-b.yml")
        self.assertIn('cron: "11-59/15 * * * *"', text)
        self.assertIn("contents: read", text)
        self.assertIn("actions: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("actions: write", text)
        self.assertIn("python -m research.watchdog", text)

    def test_new_workflows_have_no_trading_routes(self):
        for name in ("collect-phase-b.yml", "evaluate-phase-b.yml", "watchdog-phase-b.yml"):
            text = self.read(name).lower()
            for forbidden in ("place-order", "cancel-order", "set-leverage", "/api/v3/trade/", "/api/v3/position/"):
                self.assertNotIn(forbidden, text, f"{name} contains {forbidden}")


if __name__ == "__main__":
    unittest.main()
