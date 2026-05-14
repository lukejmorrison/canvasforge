#!/usr/bin/env bash
set -euo pipefail

BW_CMD=(npx -y @bitwarden/cli@2026.4.1)
ITEM_NAME="AUR maintainer SSH key - lukejmorrison"
PRIVATE_KEY="$HOME/.ssh/aur_luke_ed25519"
PUBLIC_KEY="$HOME/.ssh/aur_luke_ed25519.pub"
FINGERPRINT="SHA256:i3INXSSqTyDQlqpiDOaBsItY833BwqW3SPA/0LN/OAo"

if [[ -z "${BW_SESSION:-}" ]]; then
  echo "Error: BW_SESSION is not set in this shell." >&2
  echo 'Run: export BW_SESSION="$(npx -y @bitwarden/cli@2026.4.1 unlock --raw)"' >&2
  exit 1
fi

for path in "$PRIVATE_KEY" "$PUBLIC_KEY"; do
  if [[ ! -f "$path" ]]; then
    echo "Error: missing key file: $path" >&2
    exit 1
  fi
done

status="$("${BW_CMD[@]}" status | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))')"
if [[ "$status" != "unlocked" ]]; then
  echo "Error: Bitwarden CLI status is '$status', expected 'unlocked'." >&2
  exit 1
fi

existing_id="$("${BW_CMD[@]}" list items --search "$ITEM_NAME" |
  python3 -c '
import json
import sys

name = sys.argv[1]
items = json.load(sys.stdin)
for item in items:
    if item.get("name") == name:
        print(item.get("id", ""))
        break
' "$ITEM_NAME"
)"

if [[ -n "$existing_id" ]]; then
  echo "Bitwarden item already exists: $ITEM_NAME"
  echo "Item id: $existing_id"
  echo "No new attachments were added to avoid duplicating private-key backups."
  exit 0
fi

encoded_item="$(
  python3 - <<'PY' | "${BW_CMD[@]}" encode
import json

item = {
    "organizationId": None,
    "collectionIds": None,
    "folderId": None,
    "type": 2,
    "name": "AUR maintainer SSH key - lukejmorrison",
    "notes": (
        "Backs up the dedicated AUR maintainer SSH key for lukejmorrison.\n"
        "Host: aur.archlinux.org\n"
        "User: aur\n"
        "Private key file: ~/.ssh/aur_luke_ed25519\n"
        "Public key file: ~/.ssh/aur_luke_ed25519.pub\n"
        "Fingerprint: SHA256:i3INXSSqTyDQlqpiDOaBsItY833BwqW3SPA/0LN/OAo\n"
        "Purpose: Maintains AUR packages, currently canvasforge-beta.\n"
        "Local SSH config backup created before setup: ~/.ssh/config.bak.20260508080813"
    ),
    "favorite": False,
    "fields": [
        {"name": "Host", "value": "aur.archlinux.org", "type": 0},
        {"name": "Username", "value": "aur", "type": 0},
        {"name": "Fingerprint", "value": "SHA256:i3INXSSqTyDQlqpiDOaBsItY833BwqW3SPA/0LN/OAo", "type": 0},
        {"name": "Package", "value": "canvasforge-beta", "type": 0},
    ],
    "secureNote": {"type": 0},
}
print(json.dumps(item))
PY
)"

created_json="$("${BW_CMD[@]}" create item "$encoded_item")"
item_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$created_json")"

"${BW_CMD[@]}" create attachment --file "$PRIVATE_KEY" --itemid "$item_id" >/dev/null
"${BW_CMD[@]}" create attachment --file "$PUBLIC_KEY" --itemid "$item_id" >/dev/null

echo "Created Bitwarden item: $ITEM_NAME"
echo "Attached:"
echo "- $(basename "$PRIVATE_KEY")"
echo "- $(basename "$PUBLIC_KEY")"
echo "Item id: $item_id"
