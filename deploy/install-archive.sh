#!/usr/bin/env bash
# Set up the daily archive commit (Phase 11). Run after deploy/install.sh, as root:
#   sudo bash /opt/observatory/repo/deploy/install-archive.sh
# First run: creates the obsync user and a deploy key, prints the public key and stops.
# Add that key to GitHub (Settings -> Deploy keys -> Add deploy key -> Allow write access), then run it again.
set -euo pipefail

REPO_SSH="git@github.com:Zenithquonta/kushmodi.git"
APP=/opt/observatory
SYNC_HOME=/var/lib/obsync
KEY="$SYNC_HOME/.ssh/deploy_key"
HOSTS="$SYNC_HOME/.ssh/known_hosts"
SSH_CMD="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOSTS"

die() { echo "install-archive: $*" >&2; exit 1; }
say() { echo "==> $*"; }
as_sync() { sudo -u obsync env GIT_SSH_COMMAND="$SSH_CMD" "$@"; }

[[ $EUID -eq 0 ]] || die "run it with sudo"
[[ -x "$APP/venv/bin/python" && -d "$APP/repo/.git" ]] || die "run deploy/install.sh first"

say "sync user and archive directory"
id obsync >/dev/null 2>&1 || useradd --system --home-dir "$SYNC_HOME" --no-create-home --shell /usr/sbin/nologin obsync
install -d -o obsync -g obsync -m 700 "$SYNC_HOME" "$SYNC_HOME/.ssh"
install -d -o observatory -g observatory -m 755 /var/lib/observatory/archive

if [[ ! -s "$HOSTS" ]]; then
  say "GitHub's SSH host keys, from https://api.github.com/meta over TLS"
  keys="$(curl -fsS https://api.github.com/meta | python3 -c 'import json,sys
for key in json.load(sys.stdin)["ssh_keys"]:
    print("github.com", key)')" || die "could not fetch GitHub's host keys"
  [[ -n "$keys" ]] || die "GitHub returned no host keys"
  printf '%s\n' "$keys" > "$HOSTS.new"
  install -o obsync -g obsync -m 600 "$HOSTS.new" "$HOSTS"
  rm -f "$HOSTS.new"
fi

if [[ ! -f "$KEY" ]]; then
  say "creating the deploy key (it never leaves this server)"
  sudo -u obsync ssh-keygen -q -t ed25519 -N '' -C "kushmodi observatory archive ($(hostname))" -f "$KEY"
fi
chmod 600 "$KEY"

if ! as_sync git ls-remote "$REPO_SSH" main >/dev/null 2>&1; then
  echo
  echo "Add this public key to GitHub, then run this script again:"
  echo "  github.com/Zenithquonta/kushmodi -> Settings -> Deploy keys -> Add deploy key"
  echo "  Title: observatory archive   Key: (the line below)   [x] Allow write access"
  echo
  cat "$KEY.pub"
  echo
  exit 0
fi

if [[ ! -d "$SYNC_HOME/repo/.git" ]]; then
  say "archive-only clone (no code checked out)"
  as_sync git clone --quiet --filter=blob:none --no-checkout "$REPO_SSH" "$SYNC_HOME/repo"
  as_sync git -C "$SYNC_HOME/repo" sparse-checkout set --no-cone '/archive/'
  as_sync git -C "$SYNC_HOME/repo" checkout --quiet main
fi

say "daily timer (21:10 Mumbai time)"
install -m 644 "$APP/repo/deploy/observatory-archive.service" "$APP/repo/deploy/observatory-archive.timer" \
  "$APP/repo/deploy/observatory-sync.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --quiet --now observatory-archive.timer
systemctl list-timers observatory-archive.timer --no-pager | head -2
say "done. The first archive commit happens after the next 21:10 IST run."
echo "    To run it now:  sudo systemctl start observatory-archive.service && journalctl -u observatory-sync.service -n 20"
