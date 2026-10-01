# Live observatory on your Oracle VPS

What this sets up: every five minutes the server renders the observatory for the current moment in Mumbai and
serves exactly three files over HTTPS:

| URL | What |
| --- | --- |
| `https://<your-host>/live.svg` | animated live scene (about 1.7-2.3 MB, 1.8 MB gzipped) |
| `https://<your-host>/live.png` | still image of the same moment (840 px) |
| `https://<your-host>/live.json` | the scene state (time, season, sun, moon, planets) |

Everything else on the host returns 404. The live part never touches GitHub; the README switches to these URLs in
Phase 12. The daily archive (below) is a separate, optional step with its own key.

## Before you start (once, in the Oracle console)

1. Instance on **Ubuntu 24.04** (Ampere/ARM or x86).
2. A **reserved public IP** attached to it.
3. VCN security list: ingress **TCP 80 and 443** from `0.0.0.0/0` (keep 22, ideally limited to your IP).
4. A DNS **A record** (your domain or a free DuckDNS name) pointing at the reserved IP.
5. On the server, Oracle's own firewall must allow 80/443 (Oracle images block them even when the console allows):
   ```bash
   sudo iptables -L INPUT --line-numbers          # note the line number of the REJECT rule
   sudo iptables -I INPUT <n> -p tcp -m state --state NEW --dport 80  -j ACCEPT
   sudo iptables -I INPUT <n> -p tcp -m state --state NEW --dport 443 -j ACCEPT
   sudo apt-get install -y netfilter-persistent && sudo netfilter-persistent save
   ```
   Do not enable `ufw` as well.

## Install

```bash
git clone https://github.com/Zenithquonta/kushmodi.git
cd kushmodi
sudo bash deploy/install.sh sky.example.com      # your host name
sudo bash /opt/observatory/repo/deploy/check.sh sky.example.com
```

On a server with less than 2 GB of memory (for example Oracle's free VM.Standard.E2.1.Micro) the picture is
rendered every 15 minutes instead of 5; set `OBSERVATORY_EVERY=10` (5, 10, 15, 20, 30 or 60) before `sudo` to choose.

`install.sh` refuses to run if the system is not Ubuntu 24.04, if something other than Caddy already uses ports
80/443, or if `/etc/caddy/Caddyfile` has been customised. It is safe to run again.

What it creates:

- user `observatory` (no login, no sudo);
- `/opt/observatory/repo` (code, owned by root, read-only to the service) and `/opt/observatory/venv`;
- `/var/lib/observatory/live` (the only place the renderer may write);
- `observatory-live.timer` + `observatory-live.service` (sandboxed: no network, read-only system, no capabilities,
  CPU and memory limits);
- `/etc/caddy/Caddyfile` from `deploy/Caddyfile.template` (HTTPS certificates are automatic; the stock file is kept
  as `Caddyfile.orig`).

## Day to day

```bash
sudo bash /opt/observatory/repo/deploy/check.sh sky.example.com   # health check
sudo bash /opt/observatory/repo/deploy/update.sh                   # take the latest main (fast-forward only)
journalctl -u observatory-live.service -n 50                       # render logs
systemctl list-timers observatory-live.timer                       # next run
```

The code never updates itself: someone who could push to the repository must not be able to run code on the server
without you running `update.sh`.

## Daily archive (Phase 11)

Once a day at 21:10 Mumbai time the server renders that day's two archive frames (solar noon and 21:00, plus any of
the two days before that were missed) and commits them to `archive/` in this repository. One commit a day, never a
force-push.

```bash
sudo bash /opt/observatory/repo/deploy/install-archive.sh     # first run: creates the key and prints it
```

1. Copy the printed public key (one line starting `ssh-ed25519`).
2. On GitHub: **Zenithquonta/kushmodi -> Settings -> Deploy keys -> Add deploy key**, title `observatory archive`,
   paste the key, tick **Allow write access**, save.
3. Run the same command again. It clones an archive-only copy and enables `observatory-archive.timer`.
4. Optional: run it now with `sudo systemctl start observatory-archive.service`, then
   `journalctl -u observatory-sync.service -n 20`. The commit appears on GitHub as *Archive YYYY-MM-DD*.

How it is kept safe:

- The key is created on the server and never leaves it: `/var/lib/obsync/.ssh/deploy_key`, mode 600, owned by a
  separate user `obsync` (home 700). The renderer user cannot read it.
- Rendering runs as `observatory` with no network. The sync runs as `obsync`, only runs git and
  `deploy/archive_tool.py` from the root-owned code checkout, and copies only files named like
  `2026/2026-12-14-day.webp` that really are WebP (size-capped), plus a merged `index.json`.
- Its clone checks out `archive/` only (no code), every run starts again from `main`, and it refuses to commit
  anything outside `archive/` or more than 6 MB at once.
- GitHub's SSH host keys are taken from `https://api.github.com/meta` over TLS and pinned.

What a deploy key can and cannot do: it works for this repository only, but with write access it can push anything
to it. If the server is ever compromised, delete the key under Settings -> Deploy keys. `update.sh` shows every
non-archive change and asks before applying it, so a bad push is never run on the server unseen.

If you later protect `main` so that changes need a pull request, the archive push will be refused; allow the deploy
key to bypass the rule or keep `main` unprotected. After 2027-09-30 (the end of the configured year) the daily run
renders nothing and exits cleanly.

## Remove

```bash
sudo systemctl disable --now observatory-live.timer
sudo rm /etc/systemd/system/observatory-live.{service,timer} && sudo systemctl daemon-reload
sudo mv /etc/caddy/Caddyfile.orig /etc/caddy/Caddyfile && sudo systemctl reload caddy
sudo systemctl disable --now observatory-archive.timer 2>/dev/null; sudo rm -f /etc/systemd/system/observatory-{archive,sync}.*
sudo rm -rf /opt/observatory /var/lib/observatory /var/lib/obsync && sudo userdel observatory; sudo userdel obsync
# and delete the deploy key on GitHub (Settings -> Deploy keys)
```
