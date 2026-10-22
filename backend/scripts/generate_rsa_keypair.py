"""Creates the RS256 key pair that signs the access tokens (D4), once per
environment:

    python scripts/generate_rsa_keypair.py        (from backend/)

Writes JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH (default backend/keys/,
which git ignores). Never overwrites an existing key: rotating the keys
signs everybody out, so that is done by deleting them by hand first.
"""

import sys

from _common import utf8_output

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import backend_path, get_settings

KEY_SIZE = 3072


def main() -> int:
    settings = get_settings()
    private_path = backend_path(settings.jwt_private_key_path)
    public_path = backend_path(settings.jwt_public_key_path)
    existing = [p for p in (private_path, public_path) if p.exists()]
    if existing:
        print(f"Ya existe: {', '.join(str(p) for p in existing)}. No se sobrescribe (cerraría todas las sesiones).", file=sys.stderr)
        return 1
    key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    try:
        private_path.chmod(0o600)
    except OSError:  # Windows: the folder's ACL protects it
        pass
    public_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"Clave privada: {private_path}")
    print(f"Clave pública: {public_path}")
    return 0


if __name__ == "__main__":
    utf8_output()
    sys.exit(main())
