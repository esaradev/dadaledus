# daedalus Hermes plugin

Daedalus is now a Hermes-first treasury plugin exposed by the core `daedalus`
package. This `integrations/hermes_plugin` folder remains as a compatibility
shim for older plugin layouts, but the production path is:

```bash
git clone https://github.com/esaradev/daedalus.git
cd daedalus
python -m pip install -e .
```

The package exports `register(ctx)`, so Hermes can load the installed package
directly. It registers:

- `treasury_intake`
- `treasury_collect`
- `treasury_fulfill`
- `treasury_run_paid_audit`
- `treasury_abandon`
- `treasury_pnl`
- `treasury_open_orders`
- `treasury_evolve`
- `treasury_rollback`

It also registers session hooks that brief Hermes on the book at session start
and write an Icarus memory note at session end when `icarus-memory` is
available.

## Install into a real Hermes instance

Hermes imports plugins from its own agent runtime, so installing into only the
repo virtualenv is not enough.

```bash
git clone https://github.com/esaradev/daedalus.git
cd daedalus

# Use the Python shown by `hermes --version` if this path differs.
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python -e ".[memory]"

export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins/daedalus"
cp integrations/hermes_plugin/daedalus/plugin.yaml "$HERMES_HOME/plugins/daedalus/plugin.yaml"
cp integrations/hermes_plugin/daedalus/__init__.py "$HERMES_HOME/plugins/daedalus/__init__.py"

hermes plugins enable daedalus
hermes tools list | rg treasury
```

The successful check is:

```text
Plugin toolsets (cli):
  enabled  treasury
```

Then run the judged flow from Hermes itself:

```bash
set -a
source .env
set +a
hermes chat -t treasury --provider openrouter -m openai/gpt-4o-mini \
  -q 'Use the Daedalus treasury plugin. Call treasury_run_paid_audit for target https://developer.nvidia.com with customer "judge", human_approved true, test_collect true, evolve true. Return the order id, final state, score, Nemotron route, profit, and memory ids.'
```

## Runtime shape

Hermes is the agent runtime. Daedalus is the control plane:

```text
Hermes tool call -> quote -> Stripe Payment Link -> collect
                 -> spend gate -> live audit -> Nemotron summary
                 -> ledger -> Icarus markdown memory -> reprice
```

Use `human_approved=true` only after the human approval tap. Without it,
attended mode blocks fulfillment and records the reason.

## Optional memory

```bash
python -m pip install -e ".[memory]"
export DAEDALUS_MEMORY_ENABLED=auto
export DAEDALUS_MEMORY_ROOT=~/fabric
```

If Icarus memory is unavailable, the treasury flow still works and labels memory
as unavailable in tool results and the dashboard.
