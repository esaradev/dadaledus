# daedalus

> The financial control plane for Hermes agents that spend money to do paid work.
>
> The moment you let an agent spend, you have no idea if it is profitable.
> daedalus is the missing ledger and spend control.

Built for the Hermes Agent Accelerated Business Hackathon (NVIDIA Nemotron x
Stripe x Nous Research). Hermes is the runtime; Daedalus is the treasury it
uses to quote, collect, spend, fulfill, remember, and reprice.

## What it does

Hermes runs a real service (a website security audit) and keeps its own books:

```
Hermes tool call -> quote -> Stripe Payment Link -> collect
                 -> authorize spend -> live audit -> Nemotron summary
                 -> double-entry ledger -> Icarus markdown memory -> reprice
```

Earning is autonomous. Every outbound spend must clear three independent
protections:

1. **egress** (security) — a default-deny allowlist mirroring NemoClaw. Off-list
   host, denied. This is also emitted as a real NemoClaw `policy.yaml`.
2. **credential cap** (rail limit) — a per-vendor cap, the Stripe Projects /
   funded-wallet limit.
3. **economics** (the book) — attended approval (one human tap; the agent cannot
   self-approve) or a standing policy limit, plus a check that the realized
   funds exist.

Then Hermes reads its own P&L and reprices: raise while customers keep buying,
cut when they walk.

## The stack, and where each piece is load-bearing

- **NVIDIA Nemotron** (`nvidia/nemotron-3-ultra-550b-a55b:free` on OpenRouter)
  writes the executive summary; the audit checks and score are computed locally
  by `jobs/audit.py`. Sensitive prompts (cards, customer data, the ledger) route
  to a local Nemotron, and a sensitive call is refused rather than sent to the
  cloud when no local endpoint is set. Every structured call is wrapped in
  validate-and-retry, because Nemotron sometimes stops before it emits valid
  output.
- **Stripe** is both sides of the rail: Payment Links + the
  `checkout.session.completed` webhook to earn, and the Link / Projects / MPP
  adapters to spend, each gated by the authorization layer.
- **NemoClaw** is the egress allowlist. daedalus enforces the same default-deny
  shape standalone and emits a `policy.yaml` the real sandbox enforces.
- **Hermes** is the primary runtime. The core package exports `register(ctx)`
  and registers treasury tools (`treasury_intake`, `treasury_collect`,
  `treasury_fulfill`, `treasury_run_paid_audit`, `treasury_pnl`,
  `treasury_evolve`) plus session hooks.
- **Icarus markdown memory** is the provenance layer. When `icarus-memory` is
  installed, Daedalus writes Hermes tool calls, spend decisions, Nemotron route
  decisions, delivered reports, and repricing decisions into `~/fabric`.

## Hermes-first quickstart

```bash
./run.sh setup

# Install Daedalus into the actual Hermes agent runtime, not only this repo venv.
# `hermes --version` prints the project path if yours differs.
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python -e ".[memory]"

# Expose the Hermes plugin shim to the Hermes instance, then enable it.
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins/daedalus"
cp integrations/hermes_plugin/daedalus/plugin.yaml "$HERMES_HOME/plugins/daedalus/plugin.yaml"
cp integrations/hermes_plugin/daedalus/__init__.py "$HERMES_HOME/plugins/daedalus/__init__.py"
hermes plugins enable daedalus
hermes tools list | rg treasury
```

Ask Hermes to run the business flow with only the treasury tools:

```bash
set -a
source .env
set +a
hermes chat -t treasury --provider openrouter -m openai/gpt-4o-mini \
  -q 'Use the Daedalus treasury plugin. Call treasury_run_paid_audit for target https://developer.nvidia.com with customer "judge", human_approved true, test_collect true, evolve true. Return the order id, final state, score, Nemotron route, profit, and memory ids.'
```

For local judging without a Hermes shell:

```bash
./run.sh job https://developer.nvidia.com   # product flow, not the scripted demo
./run.sh pnl                                # five numbers from the book
```

To enable Icarus markdown memory from a clean machine:

```bash
./.venv/bin/pip install -e ".[memory]"
```

## Developer quickstart

```bash
./run.sh setup          # python 3.12 venv + deps + .env
./run.sh job <url>      # one paid audit through quote/collect/spend/audit/reprice
./run.sh demo           # scripted sponsor-story run, including three blocked spends
./run.sh test           # the full test suite
./run.sh cov            # coverage on the core modules
```

`./run.sh job` is the non-demo path: it creates a persistent order, creates or
stubs a Stripe Payment Link, books collection, runs the spend gate, audits the
target, asks Nemotron for the customer summary, writes memory if available, and
reprices from the book.

## Go live (Stripe test mode + Nemotron)

Fill `.env` (copy from `.env.example`):

```bash
STRIPE_SECRET_KEY=sk_test_...        # https://dashboard.stripe.com/test/apikeys
OPENROUTER_API_KEY=...               # https://openrouter.ai/keys  (Nemotron Ultra is free)
APPROVAL_MODE=attended               # or: policy (standing limit, no tap)
DAEDALUS_MEMORY_ENABLED=auto          # auto|true|false
DAEDALUS_MEMORY_ROOT=~/fabric         # Icarus markdown memory root
```

Then the real test-mode loop runs: `treasury_collect`/`treasury_run_paid_audit`
create a real test-mode charge for the customer payment, the Link adapter creates
a real test-mode charge for the authorized spend, and Nemotron Ultra writes the
summary. Collection is driven by the agent's tools, so no webhook server is
needed; the `stripe_earn` webhook handler stays available if you wire your own
endpoint. For a local privacy route, set `LOCAL_NEMOTRON_URL` to an
OpenAI-compatible Nemotron endpoint.

## Architecture

```
daedalus/
  config.py         one config + .env loader; PROJECT_NAME is the rename point
  ledger.py         SQLite strict double-entry; every txn sums to zero; live P&L
  spend_control.py  the gate: egress -> credential cap -> economics, in order
  egress.py         default-deny allowlist + NemoClaw policy.yaml emitter
  audit_log.py      append-only record of every spend decision
  pricing.py        quote, fulfillment budget, conversion-aware reprice
  nemotron.py       OpenRouter + local route + validate-and-retry
  orders.py         persistent order state for split Hermes tool calls
  memory.py         optional Icarus markdown-memory provenance
  jobs/audit.py     the real security-audit workload (read-only, timed)
  stripe_earn.py    payment links + webhook + idempotent booking
  stripe_spend.py   Link / Projects / MPP spend adapters
  orchestrator.py   resumable quote/collect/fulfill/job workflow
  hermes.py         Hermes register(ctx), treasury tools, schemas, hooks
  cli.py            job / demo / audit / pnl
skill/SKILL.md      Hermes skill
deploy/policy.yaml  NemoClaw egress allowlist
integrations/       compatibility shim for older Hermes plugin installs
tests/              full unit/integration suite; core modules >=90% coverage
```

## What is real vs stubbed

Real: the double-entry ledger, the three-protection gate, the audit (hits real
sites), conversion-aware pricing. With keys: Stripe test-mode charges and
Nemotron Ultra. Stubbed and clearly labelled: the Stripe Link CLI
(needs the mobile app), Stripe Projects provisioning, and MPP chain settlement
(needs a wallet/Tempo). Nothing fakes a result or moves real money.

## License

MIT.
