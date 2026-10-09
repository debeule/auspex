#!/usr/bin/env bash
# Fails if any commit in the given range is attributed to Claude: as author, as committer,
# or through a Co-Authored-By / Claude-Session trailer. Commits carry the identity of the
# person driving the work (root CLAUDE.md, Git).
# Usage: check_commit_identity.sh <base>..<head>
set -euo pipefail

range="${1:?usage: check_commit_identity.sh <base>..<head>}"
claude_identity='(^|[^a-z])claude([^a-z]|$)|@anthropic\.com'
claude_trailer='^(co-authored-by:.*(claude|@anthropic\.com)|claude-session:)'

bad=0
for sha in $(git rev-list "$range"); do
  identity=$(git log -1 --format='%an <%ae>%n%cn <%ce>' "$sha")
  if grep -qiE "$claude_identity" <<<"$identity" \
     || git log -1 --format='%B' "$sha" | grep -qiE "$claude_trailer"; then
    echo "$(git log -1 --format='%h %s' "$sha"): attributed to Claude"
    bad=1
  fi
done
exit "$bad"
