#!/usr/bin/env bash
# Install the live observatory on an Ubuntu 24.04 server.
#
#   git clone https://github.com/Zenithquonta/kushmodi.git && cd kushmodi
#   sudo bash deploy/install.sh sky.example.com
#
# Safe to run again. It refuses to touch a server where something else already serves ports 80/443 or where
# /etc/caddy/Caddyfile has been customised. It creates no GitHub credentials and opens no ports itself.
set -euo pipefail

HOST="${1:-}"
REPO_URL="https://github.com/Zenithquonta/kushmodi.git"
APP=/opt/observatory
STATE=/var/lib/observatory
LIVE="$STATE/live"
MARKER="# managed by kushmodi observatory"

die() { echo "install: $*" >&2; exit 1; }
say() { echo "==> $*"; }

[[ $EUID -eq 0 ]] || die "run it with sudo"
[[ "$HOST" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$ ]] \
  || die "usage: sudo bash deploy/install.sh sky.example.com   (a lowercase DNS name that points at this server)"
# shellcheck disable=SC1091
. /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 24.04 ]] || die "needs Ubuntu 24.04 (this is ${PRETTY_NAME:-unknown})"

listeners="$(ss -Hltnp '( sport = :80 or sport = :443 )' || true)"
if [[ -n "$listeners" && "$listeners" != *caddy* ]]; then
  die "something other than Caddy already listens on port 80 or 443:"$'\n'"$listeners"
fi
if [[ -f /etc/caddy/Caddyfile ]] && ! grep -qF "$MARKER" /etc/caddy/Caddyfile; then
  sites="$(grep -cE '^[^#[:space:]].*\{[[:space:]]*$' /etc/caddy/Caddyfile || true)"
  if ! grep -qF '/usr/share/caddy' /etc/caddy/Caddyfile || [[ "$sites" -gt 1 ]]; then
    die "/etc/caddy/Caddyfile has been customised; not overwriting it"
  fi
fi

say "installing packages"
apt-get -o DPkg::Lock::Timeout=900 update -qq
DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=900 install -y -qq git python3-venv ffmpeg caddy >/dev/null
ffmpeg -hide_banner -version | grep -q enable-librsvg || die "this ffmpeg was built without librsvg"

say "service user and directories"
id observatory >/dev/null 2>&1 || useradd --system --home-dir "$STATE" --no-create-home --shell /usr/sbin/nologin observatory
install -d -o root -g root -m 755 "$APP"
install -d -o observatory -g observatory -m 755 "$STATE" "$LIVE"

say "code (read-only to the service) in $APP/repo"
if [[ ! -d "$APP/repo/.git" ]]; then
  git clone --quiet --branch main "$REPO_URL" "$APP/repo"
fi
[[ -x "$APP/venv/bin/python" ]] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --quiet --upgrade pip
"$APP/venv/bin/pip" install --quiet -r "$APP/repo/requirements.txt"

say "systemd timer"
install -m 644 "$APP/repo/deploy/observatory-live.service" "$APP/repo/deploy/observatory-live.timer" /etc/systemd/system/
# Small servers (under 2 GB of memory, such as Oracle's E2.1.Micro with a fraction of a CPU) render every 15 minutes
# with a longer time limit instead of every 5; override with OBSERVATORY_EVERY=<minutes>.
memory_mb=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 ))
every="${OBSERVATORY_EVERY:-$(( memory_mb < 2000 ? 15 : 5 ))}"
[[ "$every" =~ ^(5|10|15|20|30|60)$ ]] || die "OBSERVATORY_EVERY must be 5, 10, 15, 20, 30 or 60"
install -d -m 755 /etc/systemd/system/observatory-live.timer.d /etc/systemd/system/observatory-live.service.d
printf '[Timer]\nOnCalendar=\nOnCalendar=*:0/%s\n' "$every" > /etc/systemd/system/observatory-live.timer.d/interval.conf
if (( every > 5 )); then
  printf '[Service]\nTimeoutStartSec=%s\n' "$(( every * 60 - 60 ))" > /etc/systemd/system/observatory-live.service.d/timeout.conf
else
  rm -f /etc/systemd/system/observatory-live.service.d/timeout.conf
fi
say "rendering every $every minutes (${memory_mb} MB of memory)"
systemctl daemon-reload
systemctl enable --quiet --now observatory-live.timer
say "first render (up to a minute or two)"
systemctl start observatory-live.service || die "first render failed: journalctl -u observatory-live.service"

say "Caddy for https://$HOST"
if [[ -f /etc/caddy/Caddyfile && ! -f /etc/caddy/Caddyfile.orig ]] && ! grep -qF "$MARKER" /etc/caddy/Caddyfile; then
  cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.orig   # keep the stock file once
fi
sed -e "s|__SITE__|$HOST|" -e "s|__ROOT__|$LIVE|" "$APP/repo/deploy/Caddyfile.template" > /etc/caddy/Caddyfile.new
caddy validate --config /etc/caddy/Caddyfile.new --adapter caddyfile >/dev/null 2>&1 || die "generated Caddyfile is invalid"
mv /etc/caddy/Caddyfile.new /etc/caddy/Caddyfile
systemctl enable --quiet caddy
systemctl reload caddy 2>/dev/null || systemctl restart caddy

say "done. Check it with: sudo bash $APP/repo/deploy/check.sh $HOST"
