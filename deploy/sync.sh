#!/usr/bin/env bash
# Commit new archive frames to GitHub once a day. Runs as the obsync user after observatory-archive.service.
# It only copies validated frames (via archive_tool.py from the read-only code checkout), commits paths under
# archive/ and pushes to main. It never runs code from its own clone and never force-pushes.
set -euo pipefail

SYNC_HOME="${SYNC_HOME:-/var/lib/obsync}"
CLONE="${SYNC_CLONE:-$SYNC_HOME/repo}"
SRC="${ARCHIVE_SRC:-/var/lib/observatory/archive}"
TOOL="${ARCHIVE_TOOL:-/opt/observatory/repo/deploy/archive_tool.py}"
BRANCH="${SYNC_BRANCH:-main}"
MAX_COMMIT_BYTES="${MAX_COMMIT_BYTES:-6000000}"
if [[ -z "${GIT_SSH_COMMAND:-}" && -f "$SYNC_HOME/.ssh/deploy_key" ]]; then
  export GIT_SSH_COMMAND="ssh -i $SYNC_HOME/.ssh/deploy_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$SYNC_HOME/.ssh/known_hosts"
fi

die() { echo "sync: $*" >&2; exit 1; }
g() { git -C "$CLONE" -c user.name="Observatory archive" -c user.email="archive@observatory.invalid" -c commit.gpgsign=false "$@"; }

for attempt in 1 2 3; do
  g fetch --quiet origin "$BRANCH"
  g checkout --quiet -B "$BRANCH" "origin/$BRANCH"   # nothing local survives between runs
  g clean -fdq -- archive
  dates="$(python3 "$TOOL" stage "$SRC" "$CLONE/archive")"
  g add -A -- archive
  if g diff --cached --quiet; then
    echo "archive already up to date"
    exit 0
  fi
  outside="$(g diff --cached --name-only | grep -v '^archive/' || true)"
  [[ -z "$outside" ]] || die "refusing to commit paths outside archive/: $outside"
  bytes=0
  while IFS= read -r -d '' path; do
    [[ -f "$CLONE/$path" ]] && bytes=$(( bytes + $(stat -c %s "$CLONE/$path") ))
  done < <(g diff --cached --name-only -z)
  (( bytes <= MAX_COMMIT_BYTES )) || die "commit would add $bytes bytes (limit $MAX_COMMIT_BYTES)"
  g commit --quiet -m "Archive ${dates:-index update}"
  if g push --quiet origin "HEAD:$BRANCH"; then
    echo "pushed: Archive ${dates:-index update} ($bytes bytes)"
    exit 0
  fi
  echo "push rejected (attempt $attempt); starting again from the new $BRANCH" >&2
  sleep $(( attempt * ${SYNC_RETRY_SECONDS:-5} ))
done
die "push failed three times"
