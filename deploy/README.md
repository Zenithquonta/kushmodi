# Live observatory on your Oracle VPS

What this sets up: every five minutes the server renders the observatory for the current moment in Mumbai and
serves exactly three files over HTTPS:

| URL | What |
| --- | --- |
| `https://<your-host>/live.svg` | animated live scene (about 1.7-2.3 MB, 1.8 MB gzipped) |
| `https://<your-host>/live.png` | still image of the same moment (840 px) |
| `https://<your-host>/live.json` | the scene state (time, season, sun, moon, planets) |

Everything else on the host returns 404. Nothing here touches GitHub yet; the README switches to these URLs in
Phase 12, and the daily archive sync (Phase 11) adds its own, separately scoped key.

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

## Remove

```bash
sudo systemctl disable --now observatory-live.timer
sudo rm /etc/systemd/system/observatory-live.{service,timer} && sudo systemctl daemon-reload
sudo mv /etc/caddy/Caddyfile.orig /etc/caddy/Caddyfile && sudo systemctl reload caddy
sudo rm -rf /opt/observatory /var/lib/observatory && sudo userdel observatory
```
