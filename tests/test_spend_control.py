"""Spend control: three protections, each the binding constraint for a case."""

import pytest

from daedalus.audit_log import AuditLog
from daedalus.egress import Egress
from daedalus.spend_control import SpendControl, mint_approval


@pytest.fixture
def gate(ledger, tmp_path):
    """A gate whose egress allows openrouter.ai, with a small per-vendor cap."""
    egress = Egress(allowed={("openrouter.ai", 443)})
    audit = AuditLog(tmp_path / "d.log")
    return SpendControl(ledger, egress=egress, audit_log=audit,
                        caps={"openrouter": 10000}, mode="attended")


def _tap(vendor, amount):
    return mint_approval(vendor, amount)


# ── each protection binds in its own case ─────────────────────────────
def test_egress_is_binding(gate, ledger):
    ledger.earn(100000)  # plenty of funds, valid token -> only egress can block
    d = gate.authorize("sketchy", "evil.example.com", 100,
                       approval_token=_tap("sketchy", 100))
    assert d.allowed is False and d.protection == "egress"


def test_credential_cap_is_binding(gate, ledger):
    ledger.earn(100000)  # funded, on allowlist, valid token -> only the cap blocks
    d = gate.authorize("openrouter", "openrouter.ai", 20000,
                       approval_token=_tap("openrouter", 20000))
    assert d.allowed is False and d.protection == "credential_cap"


def test_economics_attended_needs_tap(gate, ledger):
    ledger.earn(100000)  # funded, on allowlist, within cap, but NO tap
    d = gate.authorize("openrouter", "openrouter.ai", 500, approval_token=None)
    assert d.allowed is False and d.protection == "economics"
    assert "cannot self-approve" in d.reason


def test_economics_insufficient_funds(gate, ledger):
    # on allowlist, within cap, valid tap, but the book has no cash
    d = gate.authorize("openrouter", "openrouter.ai", 500,
                       approval_token=_tap("openrouter", 500))
    assert d.allowed is False and d.protection == "economics"
    assert "insufficient" in d.reason


def test_wrong_token_rejected(gate, ledger):
    ledger.earn(100000)
    d = gate.authorize("openrouter", "openrouter.ai", 500, approval_token="forged")
    assert d.allowed is False and d.protection == "economics"


# ── the happy path clears all three and books ─────────────────────────
def test_authorized_spend_books_cogs(gate, ledger):
    ledger.earn(2000)
    d = gate.authorize("openrouter", "openrouter.ai", 456,
                       approval_token=_tap("openrouter", 456))
    assert d.allowed is True and d.protection == "ok"
    assert ledger.balance("COGS") == 456
    assert ledger.pnl()["cash_cents"] == 2000 - 456


def test_cap_enforced_cumulatively(gate, ledger):
    # cap is 10000c; cumulative spend across calls must not exceed it
    ledger.earn(100000)
    for _ in range(21):  # 21 * 456 = 9576 < 10000; the 22nd (10032) must block
        gate.authorize("openrouter", "openrouter.ai", 456, approval_token=_tap("openrouter", 456),
                       idempotency_ref=f"s{_}")
    spent = ledger.cogs_by_vendor().get("openrouter", 0)
    d = gate.authorize("openrouter", "openrouter.ai", 456, approval_token=_tap("openrouter", 456),
                       idempotency_ref="final")
    assert d.allowed is False and d.protection == "credential_cap"
    assert spent <= 10000


def test_spend_is_idempotent(gate, ledger):
    ledger.earn(5000)
    a = gate.authorize("openrouter", "openrouter.ai", 456, approval_token=_tap("openrouter", 456),
                       idempotency_ref="spend:o1")
    b = gate.authorize("openrouter", "openrouter.ai", 456, approval_token=_tap("openrouter", 456),
                       idempotency_ref="spend:o1")  # retry, same ref
    assert a.allowed and b.allowed
    assert ledger.balance("COGS") == 456  # booked once, not twice


def test_dry_run_moves_no_money(gate, ledger):
    ledger.earn(2000)
    d = gate.authorize("openrouter", "openrouter.ai", 456, approval_token=_tap("openrouter", 456),
                       dry_run=True)
    assert d.allowed is True
    assert ledger.balance("COGS") == 0  # nothing booked


def test_decision_is_logged(gate, ledger):
    ledger.earn(2000)
    gate.authorize("openrouter", "openrouter.ai", 456, approval_token=_tap("openrouter", 456))
    gate.authorize("sketchy", "evil.example.com", 100, approval_token=_tap("sketchy", 100))
    assert gate.audit.count_blocked() == 1
    assert len(gate.audit.entries()) == 2


# ── policy mode: standing limit, no tap ───────────────────────────────
def test_policy_mode_under_limit_allows(ledger, tmp_path):
    g = SpendControl(ledger, egress=Egress(allowed={("openrouter.ai", 443)}),
                     audit_log=AuditLog(tmp_path / "p.log"),
                     caps={"openrouter": 10000}, mode="policy", policy_limit_cents=1000)
    ledger.earn(2000)
    d = g.authorize("openrouter", "openrouter.ai", 400)  # no token needed in policy mode
    assert d.allowed is True


def test_policy_mode_over_limit_blocks(ledger, tmp_path):
    g = SpendControl(ledger, egress=Egress(allowed={("openrouter.ai", 443)}),
                     audit_log=AuditLog(tmp_path / "p.log"),
                     caps={"openrouter": 10000}, mode="policy", policy_limit_cents=1000)
    ledger.earn(2000)
    d = g.authorize("openrouter", "openrouter.ai", 1500)
    assert d.allowed is False and d.protection == "economics"
    assert "policy limit" in d.reason


def test_unknown_mode_fails_closed(ledger, tmp_path):
    g = SpendControl(ledger, egress=Egress(allowed={("openrouter.ai", 443)}),
                     audit_log=AuditLog(tmp_path / "u.log"),
                     caps={"openrouter": 10000}, mode="unattended")  # typo / unrecognized mode
    ledger.earn(100000)
    d = g.authorize("openrouter", "openrouter.ai", 500, approval_token="anything")
    assert d.allowed is False and d.protection == "economics"
    assert "unknown approval mode" in d.reason


def test_nonpositive_amount_rejected(gate, ledger):
    d = gate.authorize("openrouter", "openrouter.ai", 0, approval_token=_tap("openrouter", 0))
    assert d.allowed is False
