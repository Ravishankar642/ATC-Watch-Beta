"""
Generates a VAPID (EC P-256) key pair for Web Push and prints the values to
paste into .env as VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY.

Usage:
    python scripts/generate_vapid_keys.py
"""
import base64

from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_value = private_key.private_numbers().private_value
    private_key_b64 = b64url(private_value.to_bytes(32, "big"))

    numbers = public_key.public_numbers()
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    public_key_bytes = b"\x04" + x + y
    public_key_b64 = b64url(public_key_bytes)

    print("Add these to backend/.env:\n")
    print(f"VAPID_PUBLIC_KEY={public_key_b64}")
    print(f"VAPID_PRIVATE_KEY={private_key_b64}")
    print("\nAlso add the public key to frontend/.env:")
    print(f"VITE_VAPID_PUBLIC_KEY={public_key_b64}")


if __name__ == "__main__":
    main()
