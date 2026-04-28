#!/usr/bin/env bash
# Drives realistic Redis traffic against the smoketest container so a
# running `redistail` tail can be verified end-to-end.
#
# See docs/smoketest.md for the full procedure (start container, enable
# notifications, start tail, run this script, verify, tear down).
#
# Usage:
#   ./scripts/smoketest-traffic.sh                 # against redistail-smoke on port 6399
#   CONTAINER=foo PORT=6379 ./scripts/...          # override

set -euo pipefail

CONTAINER="${CONTAINER:-redistail-smoke}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "error: container '$CONTAINER' is not running." >&2
    echo "start it with: docker run -d --name $CONTAINER -p 6399:6379 redis:7" >&2
    echo "and:           docker exec $CONTAINER redis-cli CONFIG SET notify-keyspace-events KEA" >&2
    exit 1
fi

R() { docker exec -i "$CONTAINER" redis-cli "$@" >/dev/null; }

# Strings + TTL
R SET session:u_8421 '{"user_id":8421,"email":"alice@example.com","role":"admin","scopes":["read:orders","write:orders"]}'
R EXPIRE session:u_8421 3600
R SET feature_flag:checkout_v2 '{"enabled":true,"rollout":0.35}'
R SET cache:zap "expires soon" EX 2

# Hashes
R HSET user:8421 id 8421 email alice@example.com plan enterprise mrr_cents 49900 status active
R HSET user:8421:prefs theme dark language en-US timezone America/Los_Angeles

# Lists (job queue)
R LPUSH jobs:email '{"id":"job_01HX9","type":"send_email","to":"alice@example.com"}'
R LPUSH jobs:webhooks '{"id":"wh_44","url":"https://hooks.partner.io/orders","attempts":1}'

# Sets
R SADD active_users:2025-04-28 user:8421 user:99 user:42
R SADD permissions:role:admin orders.read orders.write users.read

# Sorted sets
R ZADD leaderboard:weekly 9450 alice 8200 bob 12100 dave
R ZADD api_latency_ms:p99 12.4 GET-/orders 87.2 POST-/checkout

# Streams
R XADD stream:orders '*' order_id ord_77232 user_id 8421 total_cents 12999
R XADD stream:audit '*' actor user:8421 action refund.issue target ord_77100

# Counters / append
R INCRBY metrics:requests:GET:/api/orders 247
R INCRBYFLOAT metrics:revenue_usd 49.99
R APPEND log:requests '[2025-04-28T16:21:30Z] GET /api/orders status=200'

# Generic ops
R SET user:alice placeholder
R RENAME user:alice user:8421:legacy
R DEL session:u_old_4422

# Wait for cache:zap (EX 2) to expire so the EXPIRED event surfaces
sleep 3

echo "smoketest traffic done — check your redistail tail for ~21 events including 'EXPIRED cache:zap'"
