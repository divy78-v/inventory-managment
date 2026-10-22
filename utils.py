"""Presentation and validation helpers shared across route modules."""

from functools import wraps
from decimal import Decimal

from flask import flash, redirect, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def indian_currency(value):
    """Format a numeric value in Indian grouping, for example ₹1,25,000.00."""
    if value is None:
        value = 0
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    sign = "-" if amount < 0 else ""
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        last_three = whole[-3:]
        rest = whole[:-3]
        grouped = []
        while rest:
            grouped.insert(0, rest[-2:])
            rest = rest[:-2]
        whole = ",".join(grouped + [last_three])
    return f"{sign}₹{whole}.{fraction}"


def decimal_or_none(value):
    try:
        return Decimal(value)
    except (TypeError, ValueError):
        return None


def positive_number(value):
    number = decimal_or_none(value)
    return number if number is not None and number > 0 else None
