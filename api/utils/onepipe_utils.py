from typing import Optional


def extract_activation_url(provider_response: dict) -> Optional[str]:
    """Extract an activation/authorization URL from common provider response shapes.

    Tries, in order:
      - response["data"]["activation_url"]
      - response["activation_url"]
      - response["data"]["url"]
      - response["data"]["meta"]["activation_url"]

    Returns the first non-empty string found or None.
    """
    if not isinstance(provider_response, dict):
        return None

    data = provider_response.get("data") if isinstance(provider_response, dict) else None

    # data.activation_url
    if isinstance(data, dict):
        v = data.get("activation_url")
        if v:
            return str(v)

    # top-level activation_url
    v = provider_response.get("activation_url")
    if v:
        return str(v)

    # data.url
    if isinstance(data, dict):
        v = data.get("url")
        if v:
            return str(v)

    # data.meta.activation_url
    if isinstance(data, dict):
        meta = data.get("meta")
        if isinstance(meta, dict):
            v = meta.get("activation_url")
            if v:
                return str(v)

    return None


def extract_provider_transaction_ref(provider_response: dict) -> Optional[str]:
    """Extract a provider transaction reference from common shapes.

    Tries common keys under `data` and top-level: `transaction_ref`, `tx_ref`, `transactionId`.
    """
    if not isinstance(provider_response, dict):
        return None

    data = provider_response.get("data") if isinstance(provider_response, dict) else None

    # data.transaction_ref
    if isinstance(data, dict):
        for key in ("transaction_ref", "tx_ref", "transactionId", "transaction_id"):
            v = data.get(key)
            if v:
                return str(v)

    # top-level transaction_ref
    for key in ("transaction_ref", "tx_ref", "transactionId", "transaction_id"):
        v = provider_response.get(key)
        if v:
            return str(v)

    return None


def extract_payment_id(provider_response: dict) -> Optional[str]:
    """Extract payment_id from provider response if present."""
    if not isinstance(provider_response, dict):
        return None

    data = provider_response.get("data") if isinstance(provider_response, dict) else None
    if isinstance(data, dict):
        for key in ("payment_id", "paymentId", "payment_reference"):
            v = data.get(key)
            if v:
                return str(v)

    for key in ("payment_id", "paymentId", "payment_reference"):
        v = provider_response.get(key)
        if v:
            return str(v)

    return None
