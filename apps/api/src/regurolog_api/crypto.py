import base64
import hashlib

import qrcode  # type: ignore[import-untyped]
import qrcode.image.svg  # type: ignore[import-untyped]
from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    def __init__(self, secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as error:
            raise ValueError("Shifrlangan tokenni ochib bo‘lmadi") from error


def qr_data_url(value: str) -> str:
    image = qrcode.make(value, image_factory=qrcode.image.svg.SvgPathFillImage)
    svg = image.to_string(encoding="utf-8")
    return f"data:image/svg+xml;base64,{base64.b64encode(svg).decode('ascii')}"
