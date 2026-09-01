# 0005 — Stripe-only billing

**Status:** Accepted

## Context

The original roadmap suggested django-payments (Stripe/PayPal/Klarna). django-payments
is geared to one-off payments and is weak on the subscription lifecycle (trials,
proration, dunning, customer portal).

## Decision

**Stripe only**, integrated directly via the `stripe` library (no django-payments,
no dj-stripe). Use Stripe **Checkout** for subscribe, the **Customer Portal** for
change/cancel/invoices/payment methods, **webhooks** with idempotency for state sync,
and **Stripe Tax** for VAT/reverse-charge. Subscription state lives on the Organization.
Klarna/SEPA/cards are just Stripe payment methods. Billing is optional and disabled
when `STRIPE_SECRET_KEY` is unset.

## Consequences

- Far less billing code; Stripe owns the hard parts (portal, tax, invoices).
- PayPal etc. are out of core scope; add per project only if a customer demands it.
- All Stripe calls are isolated in `billing/services.py`, keeping views testable.
