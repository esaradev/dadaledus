"""Protection-free side of the rail: earning. Stripe Checkout / Payment Links
in TEST MODE, the checkout.session.completed webhook, and a polling fallback.

Receiving money needs no approval, so this runs fully autonomously. Booking is
idempotent: a webhook delivered twice books revenue once, keyed on the Stripe
session/payment id.

Without a key it runs a labelled stub so the loop is exercisable offline.
"""

import secrets

from . import config

try:
    import stripe
except ModuleNotFoundError:  # the plugin still loads; Stripe paths run as stubs
    stripe = None


def _sfield(obj, key, default=None):
    """Read a field from either a real Stripe object (ListObject/StripeObject use
    item access, not .get) or a plain dict. Real Stripe responses are not dicts."""
    try:
        val = obj[key]
        return default if val is None else val
    except (KeyError, TypeError, AttributeError):
        return getattr(obj, key, default)


class StripeEarn:
    def __init__(self, ledger, api_key=None, webhook_secret=None):
        self.ledger = ledger
        self.api_key = api_key if api_key is not None else config.STRIPE_SECRET_KEY
        self.webhook_secret = webhook_secret if webhook_secret is not None else config.STRIPE_WEBHOOK_SECRET
        self.enabled = bool(self.api_key) and stripe is not None
        if self.enabled:
            stripe.api_key = self.api_key

    def create_payment_link(self, amount_cents, description, order_id=""):
        if not self.enabled:
            return {"stub": True, "id": "plink_" + secrets.token_hex(4),
                    "url": f"https://checkout.test/{order_id or secrets.token_hex(3)}",
                    "amount_cents": amount_cents}
        price = stripe.Price.create(
            currency="usd", unit_amount=amount_cents,
            product_data={"name": description[:250]})
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            metadata={"order_id": order_id})
        return {"stub": False, "id": link.id, "url": link.url, "amount_cents": amount_cents}

    def charge_test(self, amount_cents, description, order_id=""):
        """Autonomous collect for the live demo: a real Stripe TEST-MODE charge
        standing in for the customer paying the link, booked idempotently. The
        production path is the Payment Link + webhook (handle_event)."""
        if not self.enabled:
            # deterministic ref per order so a retry books revenue once, not twice
            ref = f"pi_stub_{order_id}" if order_id else "pi_stub_" + secrets.token_hex(4)
            if self.ledger.has_ref(ref):
                return {"stub": True, "already_booked": True, "ref": ref}
            self.ledger.earn(int(amount_cents), ref=ref, memo=f"stub charge {order_id}")
            return {"stub": True, "ref": ref, "booked_cents": int(amount_cents)}
        # idempotency_key makes a retry reuse the same charge (same pi.id), and
        # has_ref then books revenue once. No double-charge, no double-book.
        kw = {"idempotency_key": f"collect-{order_id}"} if order_id else {}
        pi = stripe.PaymentIntent.create(
            amount=int(amount_cents), currency="usd",
            payment_method="pm_card_visa", confirm=True, off_session=True,
            description=description[:200], metadata={"order_id": order_id}, **kw)
        ref = pi.id
        if self.ledger.has_ref(ref):
            return {"already_booked": True, "ref": ref}
        self.ledger.earn(int(amount_cents), ref=ref, memo=f"stripe charge {order_id}")
        return {"booked_cents": int(amount_cents), "ref": ref, "status": pi.status}

    def verify_webhook(self, payload, sig_header):
        """Verify the Stripe signature and return the event. Raises on tamper."""
        if stripe is None:
            raise RuntimeError("stripe library not installed; cannot verify webhook signatures")
        return stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)

    def handle_event(self, event):
        """Book revenue on a completed checkout. Idempotent. Returns a result dict."""
        etype = _sfield(event, "type")
        if etype != "checkout.session.completed":
            return {"ignored": etype}
        session = event["data"]["object"]
        ref = _sfield(session, "payment_intent") or _sfield(session, "id") or ""
        amount = _sfield(session, "amount_total")
        order_id = _sfield(_sfield(session, "metadata", {}) or {}, "order_id", "")
        if amount is None:
            return {"error": "session has no amount_total"}
        if not ref:
            return {"error": "session has no payment_intent/id; refusing to book without an idempotency ref"}
        if self.ledger.has_ref(ref):
            return {"already_booked": True, "ref": ref}
        self.ledger.earn(int(amount), ref=ref, memo=f"stripe checkout {order_id}")
        return {"booked_cents": int(amount), "ref": ref, "order_id": order_id}

    def poll_paid(self, payment_link_id):
        """Has a customer paid this Payment Link? Serverless: no webhook needed.
        Returns (paid: bool, payment_intent: str, amount_cents: int|None) so the
        caller books the REAL payment (its id and amount), not a synthesized one."""
        if not self.enabled or not payment_link_id:
            return False, "", None
        sessions = stripe.checkout.Session.list(payment_link=payment_link_id, limit=1)
        data = _sfield(sessions, "data") or []
        if not data or _sfield(data[0], "payment_status") != "paid":
            return False, "", None
        s = data[0]
        return True, (_sfield(s, "payment_intent") or _sfield(s, "id") or ""), _sfield(s, "amount_total")

    def book_paid(self, order_id, payment_intent, amount_cents):
        """Book revenue for a confirmed real payment. Idempotent on the PI id."""
        ref = payment_intent or ""
        if not ref:
            return {"error": "no payment_intent to book against"}
        if self.ledger.has_ref(ref):
            return {"already_booked": True, "ref": ref}
        self.ledger.earn(int(amount_cents), ref=ref, memo=f"stripe payment {order_id}")
        return {"booked_cents": int(amount_cents), "ref": ref, "order_id": order_id}
