#!/bin/sh
set -eu

# Only modify the container's network namespace. A successful network
# firewall setup is mandatory: never proceed with unguarded egress.
for cidr in \
    0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 169.254.0.0/16 \
    172.16.0.0/12 192.168.0.0/16 198.18.0.0/15 \
    224.0.0.0/4 240.0.0.0/4; do
    iptables -w -A OUTPUT -d "$cidr" -j REJECT
done

# Block IPv6 private/link-local/loopback destinations explicitly.
for cidr in fc00::/7 fe80::/10 ::1/128; do
    ip6tables -w -A OUTPUT -d "$cidr" -j REJECT
done

# Remove network-admin privileges and switch from root to the same uid as
# the HomeServer researcher, ensuring results stay readable outside Docker.
exec setpriv --reuid=1000 --regid=1000 --clear-groups \
    --bounding-set=-net_admin \
    /opt/iwass/.venv/bin/python "$@"
