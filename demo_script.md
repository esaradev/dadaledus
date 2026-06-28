# daedalus demo script (3 minutes)

A Hermes-native plugin. Film a real Hermes session driving the treasury tools.
Setup once: `rm -rf /tmp/dae-hermes` for a clean book, then `hermes chat`.
Full screen, large font, light on dark.

## 0:00 - 0:25 — the pain

On camera: an empty Hermes session.

"Stripe just gave agents the ability to spend money. The moment you let an agent
spend, you have no idea if it is profitable, or whether it is about to pay
someone it never should. daedalus is a Hermes plugin that gives the agent a P&L
and a spend gate. Watch the agent run a business, by itself."

## 0:25 - 1:25 — the agent runs the loop

Type into Hermes:

> Run a paid security audit of https://example.com for a customer. Quote it,
> collect payment in test mode, then fulfill it.

Narrate the tool calls as Hermes makes them, live:

- "It calls `treasury_intake` — quotes the job, cost to fulfill times its markup,
  and creates a real Stripe payment link. Earning is autonomous."
- "`treasury_collect` — the customer pays, a real Stripe test charge, booked
  double-entry."

## 1:25 - 2:05 — the approval gate (the safety beat)

Hermes calls `treasury_fulfill` and the gate blocks it.

- "It tries to buy the model that writes the report. Blocked. In attended mode the
  agent cannot approve its own spend. It turns to me and asks."

Type:

> Approved.

- "Now it retries with my approval, runs the real audit on the live site, NVIDIA
  Nemotron writes the summary, and books the cost. Profit on the board."

## 2:05 - 2:35 — the five numbers

Type:

> What's our P&L?

Hermes calls `treasury_pnl`.

- "Revenue, cost, profit, blocked actions, repriced — off the agent's own
  double-entry book, which always balances to zero. This is what finance needs
  before it lets fifty agents touch a card."

(Optional second cut: in another terminal, show `dashboard.stripe.com/test/payments`
with the two real test-mode charges this run created.)

## 2:35 - 3:00 — it reprices itself, and the close

Type:

> Reprice from the book.

Hermes calls `treasury_evolve`.

- "It read its own P&L and raised its price, because margins were fat and
  customers kept paying. Earn, spend through the gate, book every dollar,
  reprice. NVIDIA Nemotron does the work, NemoClaw guards the egress, Stripe moves
  the money, and it all runs as a Hermes plugin. This is daedalus. The repo is
  open."
