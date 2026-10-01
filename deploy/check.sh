#!/usr/bin/env bash
# Confirm the live observatory works end to end:  sudo bash /opt/observatory/repo/deploy/check.sh sky.example.com
set -uo pipefail
HOST="${1:-}"
LIVE=/var/lib/observatory/live
fail=0
# report STATUS OK-MESSAGE FAIL-MESSAGE
report() {
  if [[ "$1" -eq 0 ]]; then echo "  ok    $2"; else echo "  FAIL  $3"; fail=1; fi
}

echo "service"
systemctl is-active --quiet observatory-live.timer; report $? "timer active" "timer not active"
result="$(systemctl show -p Result --value observatory-live.service)"
[[ "$result" == success ]]; report $? "last render succeeded" "last render: $result (journalctl -u observatory-live.service)"
for name in live.svg live.png live.json; do
  if [[ -f "$LIVE/$name" ]]; then
    age=$(( $(date +%s) - $(stat -c %Y "$LIVE/$name") ))
    (( age < 900 )); report $? "$name is ${age}s old ($(stat -c %s "$LIVE/$name") bytes)" "$name is ${age}s old"
  else
    report 1 "" "$name missing"
  fi
done

if [[ -n "$HOST" ]]; then
  echo "https://$HOST"
  for name in live.svg live.png live.json; do
    line="$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' "https://$HOST/$name")" || line="unreachable"
    [[ "$line" == 200* ]]; report $? "/$name -> $line" "/$name -> $line"
  done
  for path in / /index.json /.live-x/ /..%2fetc/passwd; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "https://$HOST$path")" || code="unreachable"
    [[ "$code" == 404 ]]; report $? "$path -> 404" "$path -> $code (expected 404)"
  done
fi
if (( fail == 0 )); then echo "all good"; else echo "something is wrong (see FAIL lines)"; exit 1; fi
