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

echo "weather"
systemctl is-active --quiet observatory-weather.timer; report $? "weather timer active" "weather timer not active"
if [[ -f /var/lib/observatory/weather/current.json ]]; then
  age=$(( $(date +%s) - $(stat -c %Y /var/lib/observatory/weather/current.json) ))
  (( age < 3600 )); report $? "weather fetched ${age}s ago ($(grep -o '"condition": "[a-z-]*"' /var/lib/observatory/weather/current.json))" "weather is ${age}s old (journalctl -u observatory-weather.service)"
else
  report 1 "" "no weather yet (journalctl -u observatory-weather.service)"
fi

echo "satellites"
systemctl is-active --quiet observatory-satellites.timer; report $? "satellite timer active" "satellite timer not active"
if [[ -f /var/lib/observatory/satellites/tle.json ]]; then
  age=$(( $(date +%s) - $(stat -c %Y /var/lib/observatory/satellites/tle.json) ))
  (( age < 172800 )); report $? "orbital elements fetched ${age}s ago" "orbital elements are ${age}s old (journalctl -u observatory-satellites.service)"
else
  report 1 "" "no orbital elements yet (journalctl -u observatory-satellites.service)"
fi

if id obsync >/dev/null 2>&1; then
  echo "archive"
  systemctl is-active --quiet observatory-archive.timer; report $? "archive timer active" "archive timer not active"
  [[ "$(stat -c %a /var/lib/obsync)" == 700 ]]; report $? "/var/lib/obsync is private (700)" "/var/lib/obsync is not 700"
  [[ "$(stat -c '%a %U' /var/lib/obsync/.ssh/deploy_key 2>/dev/null)" == "600 obsync" ]]
  report $? "deploy key is 600 and owned by obsync" "deploy key missing or not 600/obsync"
  for unit in observatory-archive observatory-sync; do
    result="$(systemctl show -p Result --value "$unit.service")"
    ran="$(systemctl show -p ExecMainExitTimestamp --value "$unit.service")"
    [[ "$result" == success ]]; report $? "$unit: last run ${ran:-never} succeeded" "$unit: $result (journalctl -u $unit.service)"
  done
fi

if [[ -n "$HOST" ]]; then
  echo "https://$HOST"
  for name in live.svg live.png live.json; do
    line="$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' "https://$HOST/$name")" || line="unreachable"
    [[ "$line" == 200* ]]; report $? "/$name -> $line" "/$name -> $line"
  done
  line="$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' "https://$HOST/")" || line="unreachable"
  [[ "$line" == 200*text/html* ]]; report $? "/ (the website) -> $line" "/ -> $line (expected 200 text/html)"
  for path in /js/main.js /vendor/three/three.module.js /data/stars.json /css/site.css; do
    line="$(curl -sS -o /dev/null -w '%{http_code}' "https://$HOST$path")" || line="unreachable"
    [[ "$line" == 200 ]]; report $? "$path -> 200" "$path -> $line (expected 200)"
  done
  for path in /index.json /.live-x/ /..%2fetc/passwd /data/SOURCES.md /docs/WEBSITE.md /README.md; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "https://$HOST$path")" || code="unreachable"
    [[ "$code" == 404 ]]; report $? "$path -> 404" "$path -> $code (expected 404)"
  done
fi
if (( fail == 0 )); then echo "all good"; else echo "something is wrong (see FAIL lines)"; exit 1; fi
