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
echo "==> commits:"; git log --oneline HEAD..origin/main -- . ':!archive'
echo "==> code and config changes (review these before continuing; archive frames are not listed):"
git diff --stat HEAD origin/main -- . ':!archive'
if [[ -t 0 ]]; then read -r -p "Apply these changes? [y/N] " answer; [[ "$answer" == [yY] ]] || die "not updated"; fi
git merge --quiet --ff-only origin/main || die "main has diverged from the server copy; not updating"
"$APP/venv/bin/pip" install --quiet -r requirements.txt
install -d -o observatory -g observatory -m 755 /var/lib/observatory/weather
install -m 644 deploy/observatory-live.service deploy/observatory-live.timer \
  deploy/observatory-weather.service deploy/observatory-weather.timer /etc/systemd/system/
if [[ -f /etc/systemd/system/observatory-archive.timer ]]; then
  install -m 644 deploy/observatory-archive.service deploy/observatory-archive.timer deploy/observatory-sync.service /etc/systemd/system/
fi
systemctl daemon-reload
systemctl enable --quiet --now observatory-weather.timer
systemctl start observatory-weather.service || echo "update: weather fetch failed; the seasonal model is used until it works"
systemctl start observatory-live.service
echo "==> updated to $(git log -1 --format='%h %s')"
