"""Validates Telegram WebApp `initData` per Telegram's Mini App auth spec.

Non-dev staff (director/admin/analyst) never set a password — they open the admin panel
through the bot's WebApp button, and this is how the backend turns that into a session.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InvalidInitData(Exception):
    pass


def verify_webapp_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError as exc:
        raise InvalidInitData("Malformed init data") from exc

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("Missing hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidInitData("Signature mismatch")

    auth_date = pairs.get("auth_date")
    if auth_date and time.time() - int(auth_date) > max_age_seconds:
        raise InvalidInitData("initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InvalidInitData("Missing user")

    return json.loads(user_raw)


def verify_login_widget(data: dict, bot_token: str, max_age_seconds: int = 86400) -> dict:
    """Validates the Telegram Login Widget payload (website login on a normal browser).

    Note the secret key differs from the WebApp scheme: here it's sha256(bot_token) directly,
    not HMAC('WebAppData', bot_token).
    """
    received_hash = data.get("hash")
    if not received_hash:
        raise InvalidInitData("Missing hash")

    fields = {k: v for k, v in data.items() if k != "hash" and v is not None}
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, str(received_hash)):
        raise InvalidInitData("Signature mismatch")

    auth_date = data.get("auth_date")
    if auth_date and time.time() - int(auth_date) > max_age_seconds:
        raise InvalidInitData("Login expired")

    if not data.get("id"):
        raise InvalidInitData("Missing user id")

    return data
