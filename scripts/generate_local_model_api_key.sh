#!/usr/bin/env bash
set -euo pipefail

if command -v openssl >/dev/null 2>&1; then
  token="$(openssl rand -base64 48 | tr -d '\n')"
else
  token="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
fi

cat <<EOF
LOCAL_QWEN_API_KEY=${token}

Add this value to your private .env file only. Do not commit it.
Use the same value for the backend and the local Qwen model services.
EOF
