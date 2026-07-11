"""网易云 weapi 加密（纯 Python 实现，等价于官方社区版算法）。

常量与流程来自维护版 NeteaseCloudMusicApi（Ryderwe/api-enhanced）的 util/crypto.js：
  weapi = AES-CBC(AES-CBC(text, presetKey), secretKey) + RSA(secretKey[::-1])
依赖 pycryptodome。
"""
import json
import base64
import random
import string
from Crypto.Cipher import AES

MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
    "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
    "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
    "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
    "3ece0462db0a22b8e7"
)
PUBKEY = "010001"
NONCE = b"0CoJUm6Qyw8W8jud"          # presetKey
IV = b"0102030405060708"
_BASE62 = string.ascii_letters + string.digits


def _aes_cbc(text: str, key: bytes) -> str:
    data = text.encode("utf-8")
    pad = 16 - len(data) % 16
    data += bytes([pad]) * pad
    cipher = AES.new(key, AES.MODE_CBC, IV)
    return base64.b64encode(cipher.encrypt(data)).decode("utf-8")


def _rsa(text: str) -> str:
    # secretKey 反转后做无填充 RSA，结果 hex 零填充到 256 位
    rev = text[::-1]
    m = int.from_bytes(rev.encode("utf-8"), "big")
    e = int(PUBKEY, 16)
    n = int(MODULUS, 16)
    c = pow(m, e, n)
    return format(c, "x").zfill(256)


def create_secret_key(length: int = 16) -> str:
    return "".join(random.choice(_BASE62) for _ in range(length))


def weapi(payload: dict) -> dict:
    """返回可直接 form 提交的 {params, encSecKey}。"""
    text = json.dumps(payload, separators=(",", ":"))
    secret = create_secret_key(16)
    params = _aes_cbc(_aes_cbc(text, NONCE), secret.encode("utf-8"))
    enc_sec_key = _rsa(secret)
    return {"params": params, "encSecKey": enc_sec_key}
