from decimal import Decimal


def to_onepipe_amount(naira_decimal) -> str:
    """Convert a naira amount to OnePipe amount units.

    Multiplies the given `naira_decimal` by 1000 exactly and returns the
    result as a string. Uses Decimal to avoid float rounding.

    Examples:
        to_onepipe_amount(Decimal('100000')) -> '100000000'
        to_onepipe_amount('100.25') -> '100250'
    """
    # Use string conversion to avoid binary float surprises
    dec = Decimal(str(naira_decimal))
    result = dec * Decimal(1000)
    # Render without exponent and strip trailing zeros from fractional part
    s = format(result, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s
