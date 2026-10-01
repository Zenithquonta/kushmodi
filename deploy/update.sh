#!/usr/bin/env bash
# Update the renderer on the server to the latest main (fast-forward only), then render once.
#   sudo bash /opt/observatory/repo/deploy/update.sh
# Code never updates itself: run this when you want a new version live.
set -euo pipefail
APP=/opt/observatory
die() { echo "update: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run it with sudo"
cd "$APP/repo"
git fetch --quiet origin main
echo "==> changes:"; git log --oneline HEAD..origin/main
git merge --quiet --ff-only origin/main || die "main has diverged from the server copy; not updating"
"$APP/venv/bin/pip" install --quiet -r requirements.txt
install -m 644 deploy/observatory-live.service deploy/observatory-live.timer /etc/systemd/system/
systemctl daemon-reload
systemctl start observatory-live.service
echo "==> updated to $(git log -1 --format='%h %s')"
