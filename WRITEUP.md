# daedalus — submission writeup

## The pain

Stripe gave agents the ability to spend. NVIDIA gave them the compute to run long
operations. Nobody gave them a way to know whether any of it makes money, or a
way to stop an agent from paying someone it never should. Give a Hermes agent the
Stripe skill today and it can buy APIs and provision SaaS, but it has no books, no
margin, no per-vendor cap, no audit trail.

## The wedge

daedalus is the missing ledger and spend control for any agent that spends to
earn. Hermes runs a real service, a website security audit, and daedalus is the
treasury it must use. Hermes prices the job, earns through Stripe, and to
fulfill it must buy inputs through an authorization gate. Every spend clears
three independent protections, in order:

1. egress — a default-deny allowlist mirroring NemoClaw. Off-list host, denied.
2. credential cap — the per-vendor Stripe Projects / funded-wallet limit.
3. economics — attended approval (one human tap; the agent cannot self-approve)
   or a standing policy limit, plus a check that the realized funds exist.

Then it reads its own double-entry book, writes the decision trail into Icarus
markdown memory, and reprices: raise while customers keep paying, cut when they
walk.

## The stack

- NVIDIA Nemotron 3 Ultra (free on OpenRouter) writes the executive summary; the
  audit checks and score are computed locally; sensitive prompts route to a local
  Nemotron or are refused rather than sent to the cloud; every structured call is
  wrapped in validate-and-retry.
- Stripe is both sides of the rail: Payment Links and the webhook to earn, the
  Link / Projects / MPP adapters to spend.
- NemoClaw is the egress layer; daedalus emits the policy.yaml the sandbox runs.
- Hermes drives it through registered treasury tools, not a sidecar script.
- Icarus markdown memory records the Hermes tool calls, spend decisions,
  Nemotron route decisions, delivered report, and pricing changes.

## The numbers

Hermes runs the whole loop through the treasury tools: a real live audit, one
approval-gated spend, explicit blocks with reasons logged, a double-entry book
that balances to zero, and the five numbers from `treasury_pnl`: revenue, cost,
profit, blocked actions, repriced. Standalone-runnable with no keys; real Stripe
test mode and Nemotron with keys.

## Coming soon

Unattended spend over the Machine Payments Protocol against a pre-funded wallet,
real Stripe Projects provisioning, and a fleet view across many agents on one
book. daedalus drops into any Hermes agent and gives it a P&L.

Repo: github.com/esaradev/daedalus
