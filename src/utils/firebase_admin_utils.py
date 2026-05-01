"""
Firebase Admin SDK initialization and helper functions.

Place your Firebase service account JSON file at one of:
  - firebase-service-account.json (project root)
  - Set environment variable FIREBASE_SERVICE_ACCOUNT_PATH to the file path
  - Set environment variable FIREBASE_SERVICE_ACCOUNT_JSON to the raw JSON content
"""

import os
import json
from pathlib import Path
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials


# Paths to search for the service account file
_SERVICE_ACCOUNT_PATHS = [
    Path("firebase-service-account.json"),
    Path("firebase-admin-sdk.json"),
    Path("service-account.json"),
]


def _find_service_account() -> dict | str:
    """Find and load the Firebase service account credentials.

    Returns either a dict (parsed JSON) or a string (file path).
    Raises FileNotFoundError if no credentials are found.
    """
    # 1. Check env var for raw JSON
    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        return json.loads(raw_json)

    # 2. Check env var for file path
    env_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 3. Search common locations
    for path in _SERVICE_ACCOUNT_PATHS:
        if path.exists():
            return str(path)

    raise FileNotFoundError(
        "Firebase service account not found. "
        "Place it at 'firebase-service-account.json' in the project root, "
        "or set FIREBASE_SERVICE_ACCOUNT_PATH / FIREBASE_SERVICE_ACCOUNT_JSON env vars."
    )


@lru_cache(maxsize=1)
def _get_app() -> firebase_admin.App:
    """Initialize and return the Firebase Admin app (cached singleton)."""
    creds_data = _find_service_account()

    if isinstance(creds_data, dict):
        cred = credentials.Certificate(creds_data)
    else:
        cred = credentials.Certificate(creds_data)

    return firebase_admin.initialize_app(cred)


def get_admin_auth() -> auth:
    """Return the Firebase Admin auth module, initializing the app if needed."""
    _get_app()
    return auth


def verify_id_token(token: str) -> dict:
    """Verify a Firebase ID token and return the decoded claims.

    Args:
        token: The ID token string from the client.

    Returns:
        dict with keys: uid, email, role (custom claim), etc.

    Raises:
        firebase_admin.auth.InvalidIdTokenError: If token is invalid/expired.
        ValueError: If token is empty or None.
    """
    if not token:
        raise ValueError("Token is required")

    decoded = get_admin_auth().verify_id_token(token)
    return decoded


def set_user_role(uid: str, role: str) -> dict:
    """Set a custom claim 'role' on a Firebase user.

    Args:
        uid: The Firebase user UID.
        role: One of 'admin', 'employee', 'supplier'.

    Returns:
        The decoded token with new claims (for verification).
    """
    valid_roles = {"admin", "employee", "supplier"}
    if role not in valid_roles:
        raise ValueError(f"Invalid role '{role}'. Must be one of: {valid_roles}")

    admin_auth = get_admin_auth()
    admin_auth.set_custom_user_claims(uid, {"role": role})

    # Return updated state for confirmation
    user = admin_auth.get_user(uid)
    return {
        "uid": uid,
        "role": role,
        "custom_claims": user.custom_claims,
    }


def get_user_role(uid: str) -> str | None:
    """Get the role custom claim for a user.

    Args:
        uid: The Firebase user UID.

    Returns:
        The role string or None if not set.
    """
    user = get_admin_auth().get_user(uid)
    claims = user.custom_claims or {}
    return claims.get("role")