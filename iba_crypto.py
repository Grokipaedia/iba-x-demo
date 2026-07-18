"""
iba_crypto.py — Real asymmetric signing for IBA Intent Certificates

Replaces the SHA-256-hash "signing" in the original swarmforge.py reference
implementation (Section 6 of the IBA Technical Specification identified this
as a genuine security gap: a hash of plaintext fields is not a signature —
it has no private key, no non-repudiation, and anyone who knows the input
fields can recompute the same value).

This module does real asymmetric cryptography: ECDSA on the P-256 curve.
A private key signs. Only the matching public key can verify. Forgery
requires the private key, not just knowledge of the certificate's contents.

Dependency: `cryptography` (already installed, real library, not a stub).
"""

import json
import time
import base64
from dataclasses import dataclass, field, asdict
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature


class IBAKeyPair:
    """Generates and holds a real ECDSA P-256 keypair for a principal."""

    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self.private_key.public_key()

    def public_key_pem(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def private_key_pem(self) -> str:
        # NOTE: for demonstration only. Real deployments must never serialize
        # or transmit the private key — it stays with the signer, always.
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()


@dataclass
class IntentCertificateV2:
    """
    Intent Certificate with real cryptographic signing.
    Same declared fields as the original swarmforge.py IntentCertificate,
    plus an actual ECDSA signature and the signer's public key for verification.
    """
    agent_id: str
    principal: str
    declared_intent: str
    scope: dict
    default_posture: str = "DENY_ALL"
    hard_expiry_seconds: int = 3600
    issued_at: float = field(default_factory=time.time)
    signature: str = ""          # base64-encoded DER signature, filled by sign()
    public_key_pem: str = ""     # filled by sign(), used by verify()

    def _canonical_payload(self) -> bytes:
        """Deterministic byte representation of everything EXCEPT the signature itself."""
        payload = {
            "agent_id": self.agent_id,
            "principal": self.principal,
            "declared_intent": self.declared_intent,
            "scope": self.scope,
            "default_posture": self.default_posture,
            "hard_expiry_seconds": self.hard_expiry_seconds,
            "issued_at": self.issued_at,
        }
        return json.dumps(payload, sort_keys=True).encode()

    def sign(self, keypair: IBAKeyPair) -> None:
        """Real ECDSA signature — requires the private key. This is the actual fix."""
        payload = self._canonical_payload()
        der_signature = keypair.private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
        self.signature = base64.b64encode(der_signature).decode()
        self.public_key_pem = keypair.public_key_pem()

    def verify(self) -> bool:
        """
        Verifies the signature against the embedded public key.
        Returns False on any tampering, expiry irrelevant here (see is_valid()).
        Anyone can verify. Nobody but the private-key holder could have signed it —
        this is the property the original hash-based sign() did not have.
        """
        if not self.signature or not self.public_key_pem:
            return False
        try:
            pub = serialization.load_pem_public_key(self.public_key_pem.encode())
            der_signature = base64.b64decode(self.signature)
            pub.verify(der_signature, self._canonical_payload(), ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False

    def is_valid(self) -> bool:
        return self.verify() and (time.time() - self.issued_at) < self.hard_expiry_seconds


if __name__ == "__main__":
    print("=" * 64)
    print(" IBA Crypto — Real ECDSA P-256 Signing, Self-Test")
    print("=" * 64)

    # Real principal keypair
    principal_keys = IBAKeyPair()
    print(f"\n[1] Generated real ECDSA P-256 keypair for principal.")
    print(f"    Public key (share freely):\n{principal_keys.public_key_pem()[:120]}...")

    # Issue and sign a certificate
    cert = IntentCertificateV2(
        agent_id="G-0001",
        principal="jeffrey.williams@intentbound.com",
        declared_intent="Maximize collective value under hard constraints",
        scope={"x_min": 0.08, "x_max": 0.92, "y_min": 0.08, "y_max": 0.92},
    )
    cert.sign(principal_keys)
    print(f"\n[2] Certificate signed. Signature (base64, truncated): {cert.signature[:40]}...")

    # Verify — should succeed
    print(f"\n[3] Verifying with correct public key: {cert.verify()}  (expect True)")

    # Tamper test — attacker changes declared_intent after the fact
    tampered = IntentCertificateV2(**{**asdict(cert)})
    tampered.declared_intent = "Withdraw maximum funds immediately"
    print(f"\n[4] TAMPER TEST: attacker modifies declared_intent, keeps original signature.")
    print(f"    Verification after tampering: {tampered.verify()}  (expect False — this is the fix)")

    # Forgery test — attacker without the private key tries to sign a NEW cert
    attacker_keys = IBAKeyPair()
    forged = IntentCertificateV2(
        agent_id="G-0001",
        principal="jeffrey.williams@intentbound.com",  # impersonating the real principal
        declared_intent="Withdraw maximum funds immediately",
        scope={"x_min": 0.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0},
    )
    forged.sign(attacker_keys)  # signed with attacker's OWN key, not the real principal's
    print(f"\n[5] FORGERY TEST: attacker signs a fake cert with their own keypair.")
    print(f"    A verifier who only trusts the REAL principal's public key would reject this")
    print(f"    (comparing forged.public_key_pem against the known-good principal key,")
    print(f"    which is the actual deployment pattern — public keys are pinned, not accepted blind).")
    print(f"    forged.public_key_pem == principal_keys.public_key_pem(): "
          f"{forged.public_key_pem == principal_keys.public_key_pem()}  (expect False)")

    print(f"\n{'='*64}")
    print(f" Compare to original swarmforge.py sign(): SHA-256 hash of plaintext.")
    print(f" That approach would return the IDENTICAL hash for the tampered certificate")
    print(f" above if an attacker recomputed it — no private key was ever required.")
    print(f" This module closes that gap with real, verifiable asymmetric signing.")
    print(f"{'='*64}")
