#!/bin/bash
set -e

"$@" /nomad-dns-exporter/nomad-dns-exporter.py --nomad_server=${NOMAD_SERVER} --dns_hostname=${DNS_HOSTNAME} --dns_port=${DNS_PORT} --dns_ttl_secs=${DNS_TTL} --http_hostname=${HTTP_HOSTNAME} --http_port=${HTTP_PORT} --nomad_domain=${NOMAD_DOMAIN} --alsologtostderr
