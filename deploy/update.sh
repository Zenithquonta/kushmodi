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
install -d -o observatory -g observatory -m 755 /var/lib/observatory/weather /var/lib/observatory/satellites
install -m 644 deploy/observatory-live.service deploy/observatory-live.timer \
  deploy/observatory-weather.service deploy/observatory-weather.timer \
  deploy/observatory-satellites.service deploy/observatory-satellites.timer /etc/systemd/system/
if [[ -f /etc/systemd/system/observatory-archive.timer ]]; then
  install -m 644 deploy/observatory-archive.service deploy/observatory-archive.timer deploy/observatory-sync.service /etc/systemd/system/
fi
# Re-render the Caddy site (the live files and the website in site/) for the host this server already serves.
MARKER="# managed by kushmodi observatory"
if grep -qF "$MARKER" /etc/caddy/Caddyfile 2>/dev/null; then
  HOST="$(grep -m1 -E '^[a-z0-9.-]+ \{[[:space:]]*$' /etc/caddy/Caddyfile | cut -d' ' -f1)"
  if [[ "$HOST" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$ ]]; then
    sed -e "s|__SITE__|$HOST|" -e "s|__ROOT__|/var/lib/observatory/live|" -e "s|__SITE_ROOT__|$APP/repo/site|" \
      deploy/Caddyfile.template > /etc/caddy/Caddyfile.new
    if caddy validate --config /etc/caddy/Caddyfile.new --adapter caddyfile >/dev/null 2>&1; then
      mv /etc/caddy/Caddyfile.new /etc/caddy/Caddyfile
      systemctl reload caddy 2>/dev/null || systemctl restart caddy
    else
      rm -f /etc/caddy/Caddyfile.new
      echo "update: the generated Caddyfile is invalid; Caddy was left as it was"
    fi
  else
    echo "update: could not read the host name from /etc/caddy/Caddyfile; Caddy was left as it was"
  fi
fi
systemctl daemon-reload
systemctl enable --quiet --now observatory-weather.timer observatory-satellites.timer
systemctl start observatory-weather.service || echo "update: weather fetch failed; the seasonal model is used until it works"
systemctl start observatory-satellites.service || echo "update: satellite fetch failed; no satellites are drawn until it works"
systemctl start observatory-live.service
echo "==> updated to $(git log -1 --format='%h %s')"
