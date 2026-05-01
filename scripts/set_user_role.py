#!/usr/bin/env python3
"""Admin script to set a Firebase user's role via custom claims.

Usage:
    python scripts/set_user_role.py <uid> <role>

Examples:
    python scripts/set_user_role.py abc123def456 admin
    python scripts/set_user_role.py xyz789ghi012 employee
    python scripts/set_user_role.py mno345pqr678 supplier

Prerequisites:
    - A Firebase service account JSON file in the project root
      (firebase-service-account.json), or set the env var
      FIREBASE_SERVICE_ACCOUNT_PATH / FIREBASE_SERVICE_ACCOUNT_JSON.
"""

import sys
import os

# Ensure the project root is on sys.path so we can import src modules
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/set_user_role.py <uid> <role>")
        print("Example: python scripts/set_user_role.py abc123def456 admin")
        sys.exit(1)

    uid = sys.argv[1].strip()
    role = sys.argv[2].strip().lower()

    valid_roles = {"admin", "employee", "supplier"}
    if role not in valid_roles:
        print(f"❌ Invalid role '{role}'. Must be one of: {sorted(valid_roles)}")
        sys.exit(1)

    from src.utils.firebase_admin_utils import set_user_role

    try:
        result = set_user_role(uid, role)
        print(f"✅ Successfully set role '{role}' for user {uid}")
        print(f"   Custom claims: {result['custom_claims']}")
    except Exception as e:
        print(f"❌ Failed to set role: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()