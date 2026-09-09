#!/usr/bin/env bash
# Refuse to let credential-shaped content reach a public repository.
#
# Runs over every file the next `git add -A` would stage: tracked files, plus
# untracked ones that .gitignore does not cover. Tracked-only was the earlier
# rule and it had a hole — a brand-new file is invisible until it is staged, so
# the scanner reported a clean tree that failed the moment it was committed.
# Anything gitignored is still skipped; scratch files in ignored paths remain
# the operator's business.
#
# A file that legitimately contains credential-shaped text (this scanner, the
# redaction code, their tests, the security docs) declares itself by including
# the marker below. Self-declaration beats a central exclude list, which drifts
# out of sync the moment someone adds a test.
#
# Exit codes: 0 clean, 1 findings.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

MARKER='PFA-ALLOW-SECRET-FIXTURES'

# Patterns are credential SHAPES, not keywords: matching on the word "token"
# produces noise, matching on a 40-character `ghp_` string does not.
PATTERNS=(
  'sk-[A-Za-z0-9_-]{20,}'
  'gh[pousr]_[A-Za-z0-9]{30,}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
  '[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}'
  'AKIA[0-9A-Z]{16}'
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  'postgres(ql)?://[^:]+:[^@]{6,}@'
)

status=0
scanned=0
declare -a to_scan=()

while IFS= read -r file; do
  [ -f "$file" ] || continue
  # Skip binaries and self-declared fixture files.
  if grep -qI "$MARKER" "$file" 2>/dev/null; then
    continue
  fi
  to_scan+=("$file")
done < <(git ls-files --cached --others --exclude-standard)

scanned=${#to_scan[@]}
if [ "$scanned" -eq 0 ]; then
  echo "secrets-check: no files to scan"
  exit 0
fi

for pattern in "${PATTERNS[@]}"; do
  if matches=$(grep -nEI "$pattern" "${to_scan[@]}" 2>/dev/null); then
    echo "SECRET-SHAPED CONTENT FOUND (pattern: $pattern)"
    echo "$matches"
    status=1
  fi
done

# A committed .env is always wrong, whatever it contains.
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "FAIL: .env is tracked by git. Run: git rm --cached .env"
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "secrets-check: clean ($scanned files scanned, tracked and stageable)"
else
  echo
  echo "Refusing to consider this tree publishable."
  echo "If a match is a deliberate test fixture, add the marker $MARKER"
  echo "in a comment in that file. Otherwise remove the credential."
fi
exit "$status"
