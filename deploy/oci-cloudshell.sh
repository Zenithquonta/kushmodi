#!/usr/bin/env bash
# One-shot Oracle Cloud setup for the live observatory. Run it in Oracle Cloud Shell (the >_ icon at the top of the
# Oracle console), which is already signed in to your account:
#
#   curl -fsSL https://raw.githubusercontent.com/Zenithquonta/kushmodi/main/deploy/oci-cloudshell.sh -o oci.sh
#   bash oci.sh
#
# It creates a network "observatory-net" (ports 22, 80, 443 open), an Ubuntu 24.04 instance "observatory"
# (free Ampere A1 if Oracle has capacity, otherwise the free E2.1.Micro), points your DuckDNS name at it, and lets
# the instance install itself on first boot (deploy/install.sh). Your DuckDNS token is used here only, to update the
# address; it is not stored on the instance or anywhere else. Safe to run again: existing pieces are reused.
set -euo pipefail

C="${OCI_TENANCY:-}"
NAME=observatory
die() { echo "oci-cloudshell: $*" >&2; exit 1; }
say() { echo "==> $*"; }
command -v oci >/dev/null || die "run this in Oracle Cloud Shell (the >_ icon in the Oracle console)"
[[ -n "$C" ]] || die "OCI_TENANCY is not set; run this in Oracle Cloud Shell"

read -r -p "DuckDNS name (the part before .duckdns.org): " SUB
SUB="$(echo "$SUB" | tr '[:upper:]' '[:lower:]' | sed 's/\.duckdns\.org$//')"
[[ "$SUB" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]] || die "that is not a valid DuckDNS name"
read -r -s -p "DuckDNS token (shown at the top of duckdns.org after you sign in; input is hidden): " TOKEN; echo
[[ "$TOKEN" =~ ^[0-9a-fA-F-]{36}$ ]] || die "that does not look like a DuckDNS token"
HOST="$SUB.duckdns.org"

first() { oci "$@" --all --query 'data[0].id' --raw-output 2>/dev/null || true; }

say "network"
VCN="$(first network vcn list --compartment-id "$C" --display-name observatory-net --lifecycle-state AVAILABLE)"
if [[ -z "$VCN" || "$VCN" == null ]]; then
  VCN="$(oci network vcn create --compartment-id "$C" --display-name observatory-net --dns-label obsnet \
    --cidr-blocks '["10.20.0.0/16"]' --wait-for-state AVAILABLE --query data.id --raw-output)"
fi
IGW="$(first network internet-gateway list --compartment-id "$C" --vcn-id "$VCN" --lifecycle-state AVAILABLE)"
if [[ -z "$IGW" || "$IGW" == null ]]; then
  IGW="$(oci network internet-gateway create --compartment-id "$C" --vcn-id "$VCN" --is-enabled true \
    --display-name observatory-igw --wait-for-state AVAILABLE --query data.id --raw-output)"
fi
RT="$(oci network vcn get --vcn-id "$VCN" --query 'data."default-route-table-id"' --raw-output)"
oci network route-table update --rt-id "$RT" --force \
  --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"$IGW\"}]" >/dev/null
SL="$(first network security-list list --compartment-id "$C" --vcn-id "$VCN" --display-name observatory-web --lifecycle-state AVAILABLE)"
rule() { echo "{\"source\":\"0.0.0.0/0\",\"protocol\":\"6\",\"isStateless\":false,\"tcpOptions\":{\"destinationPortRange\":{\"min\":$1,\"max\":$1}}}"; }
INGRESS="[$(rule 22),$(rule 80),$(rule 443)]"
EGRESS='[{"destination":"0.0.0.0/0","protocol":"all","isStateless":false}]'
if [[ -z "$SL" || "$SL" == null ]]; then
  SL="$(oci network security-list create --compartment-id "$C" --vcn-id "$VCN" --display-name observatory-web \
    --ingress-security-rules "$INGRESS" --egress-security-rules "$EGRESS" --wait-for-state AVAILABLE --query data.id --raw-output)"
fi
SUBNET="$(first network subnet list --compartment-id "$C" --vcn-id "$VCN" --display-name observatory-public --lifecycle-state AVAILABLE)"
if [[ -z "$SUBNET" || "$SUBNET" == null ]]; then
  SUBNET="$(oci network subnet create --compartment-id "$C" --vcn-id "$VCN" --display-name observatory-public \
    --dns-label pub --cidr-block 10.20.0.0/24 --route-table-id "$RT" --security-list-ids "[\"$SL\"]" \
    --wait-for-state AVAILABLE --query data.id --raw-output)"
fi

say "first-boot install script"
[[ -f "$HOME/.ssh/id_ed25519" ]] || ssh-keygen -q -t ed25519 -N '' -f "$HOME/.ssh/id_ed25519"
BOOT="$(mktemp)"
cat > "$BOOT" <<BOOTSTRAP
#!/bin/bash
exec > /var/log/observatory-bootstrap.log 2>&1
set -x
line=\$(iptables -L INPUT --line-numbers | awk '\$2=="REJECT" {print \$1; exit}')
if [ -n "\$line" ]; then
  iptables -I INPUT "\$line" -p tcp -m state --state NEW --dport 443 -j ACCEPT
  iptables -I INPUT "\$line" -p tcp -m state --state NEW --dport 80 -j ACCEPT
fi
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=900 update -qq
apt-get -o DPkg::Lock::Timeout=900 install -y -qq netfilter-persistent git
netfilter-persistent save
git clone --quiet https://github.com/Zenithquonta/kushmodi.git /root/kushmodi
bash /root/kushmodi/deploy/install.sh $HOST
sleep 120
bash /opt/observatory/repo/deploy/check.sh $HOST
echo OBSERVATORY-BOOTSTRAP-FINISHED
BOOTSTRAP

say "instance (Ubuntu 24.04)"
INST="$(first compute instance list --compartment-id "$C" --display-name "$NAME" --lifecycle-state RUNNING)"
if [[ -z "$INST" || "$INST" == null ]]; then
  AD="$(oci iam availability-domain list --compartment-id "$C" --query 'data[0].name' --raw-output)"
  image_for() {   # the backticks below are JMESPath literals, not shell
    # shellcheck disable=SC2016
    oci compute image list --compartment-id "$C" --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
      --shape "$1" --sort-by TIMECREATED --sort-order DESC --all \
      --query 'data[?!contains("display-name", `Minimal`)] | [0].id' --raw-output
  }
  launch() {   # shape, extra args...
    local shape="$1"; shift
    oci compute instance launch --compartment-id "$C" --availability-domain "$AD" --display-name "$NAME" \
      --shape "$shape" "$@" --image-id "$(image_for "$shape")" --subnet-id "$SUBNET" --assign-public-ip true \
      --ssh-authorized-keys-file "$HOME/.ssh/id_ed25519.pub" --user-data-file "$BOOT" \
      --wait-for-state RUNNING --query data.id --raw-output
  }
  say "trying the free Ampere A1 (1 OCPU, 6 GB)"
  if ! INST="$(launch VM.Standard.A1.Flex --shape-config '{"ocpus":1,"memoryInGBs":6}' 2>/tmp/a1.err)"; then
    if grep -qi capacity /tmp/a1.err; then
      say "no Ampere capacity right now; using the free E2.1.Micro"
    else
      cat /tmp/a1.err >&2
      say "Ampere launch failed (above); trying the free E2.1.Micro"
    fi
    INST="$(launch VM.Standard.E2.1.Micro)"
  fi
fi
rm -f "$BOOT"
IP="$(oci compute instance list-vnics --instance-id "$INST" --query 'data[0]."public-ip"' --raw-output)"
[[ "$IP" =~ ^[0-9.]+$ ]] || die "the instance has no public IP"

say "DuckDNS: $HOST -> $IP"
answer="$(curl -fsS "https://www.duckdns.org/update?domains=$SUB&token=$TOKEN&ip=$IP")" || die "could not reach DuckDNS"
[[ "$answer" == OK ]] || die "DuckDNS refused the update (check the name exists in your DuckDNS account and the token)"

cat <<DONE

Done. The instance is installing itself now (about 10-20 minutes on the Micro, faster on Ampere).

  Watch it:   ssh -i ~/.ssh/id_ed25519 ubuntu@$IP 'tail -f /var/log/observatory-bootstrap.log'
  Finished when the log ends with OBSERVATORY-BOOTSTRAP-FINISHED and "all good".
  Then open:  https://$HOST/live.png

Send this to Claude:  host $HOST, and the last 25 lines of that log:
  ssh -i ~/.ssh/id_ed25519 ubuntu@$IP 'tail -n 25 /var/log/observatory-bootstrap.log'
DONE
