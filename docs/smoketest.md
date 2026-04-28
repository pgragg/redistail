# Local smoketest

A repeatable end-to-end check that an installed `redistail` works against a
real Redis. Useful after changes to the subscriber, filters, or renderer,
and before cutting a release.

The whole thing takes ~30 seconds and leaves nothing behind once you tear
the container down.

## Prerequisites

- Docker running locally
- `redistail` on `$PATH` (see [Install for global use](#install-for-global-use) below)

## 1. Start a throwaway Redis

We use port **6399** to avoid colliding with any local Redis on 6379.

```bash
docker run -d --name redistail-smoke -p 6399:6379 redis:7
docker exec redistail-smoke redis-cli CONFIG SET notify-keyspace-events KEA
docker exec redistail-smoke redis-cli CONFIG GET notify-keyspace-events
# → 1) "notify-keyspace-events"
#   2) "AKE"
```

## 2. Tail it (terminal A)

```bash
redistail redis://localhost:6399
```

Expected first line:

```
redistail → redis 7.x.x (standalone, role=master, user=default). Source: keyspace notifications (db=0). Ctrl-C to stop.
```

Leave this running.

> **Pub/sub has no replay.** Any writes that happened *before* this command
> started will not appear. Always start the tail first, then drive traffic.

## 3. Drive realistic traffic (terminal B)

Save this as `scripts/smoketest-traffic.sh` (or run it ad-hoc). It
exercises every Redis data type plus TTL expiry and rename:

```bash
#!/usr/bin/env bash
set -e
R() { docker exec -i redistail-smoke redis-cli "$@" >/dev/null; }

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

# Wait for cache:zap to expire
sleep 3
echo "smoketest traffic done"
```

Make it executable once and run it:

```bash
chmod +x scripts/smoketest-traffic.sh
./scripts/smoketest-traffic.sh
```

> **Quoting note.** Don't try to inline JSON values via a heredoc with
> `<<EOF` — bash's variable expansion + nested double quotes silently
> mangle the payloads and `redis-cli` ends up storing nothing. Use
> single-quoted args via the `R()` helper above. (We hit this exact bug
> while authoring this doc.)

## 4. Verify (terminal A)

You should see all of these events scroll by, ordered roughly as fired:

```
SET      session:u_8421
EXPIRE   session:u_8421
SET      feature_flag:checkout_v2
SET      cache:zap
EXPIRE   cache:zap
HSET     user:8421
HSET     user:8421:prefs
LPUSH    jobs:email
LPUSH    jobs:webhooks
SADD     active_users:2025-04-28
SADD     permissions:role:admin
ZADD     leaderboard:weekly
ZADD     api_latency_ms:p99
XADD     stream:orders
XADD     stream:audit
INCRBY   metrics:requests:GET:/api/orders
INCRBYFLOAT metrics:revenue_usd
APPEND   log:requests
SET      user:alice
RENAME_FROM user:alice
RENAME_TO user:8421:legacy
EXPIRED  cache:zap        ← arrives ~2s after SET cache:zap
```

### Pass criteria

- ✅ Header line shows correct Redis version and `db=0`
- ✅ Every data type from §3 produces an event
- ✅ `RENAME_FROM` + `RENAME_TO` are paired
- ✅ `EXPIRED cache:zap` arrives ~2s after the `SET … EX 2`
- ✅ No stack traces in either terminal

If you see only `set,del,expire,expired` events and nothing else, you're
on an older redistail where the default `--ops` was a narrow allowlist.
The current default is `--ops all`. Either upgrade or run:

```bash
redistail --ops all redis://localhost:6399
```

### Optional: with values

To verify `--with-values` does the follow-up read correctly:

```bash
redistail --with-values --max-width 200 redis://localhost:6399
```

Re-run the traffic script. JSON blobs, hash fields, list/set/zset/stream
contents should appear inline next to each event.

## 5. Tear down

```bash
docker rm -f redistail-smoke
```

That's it — no host config, no leftover volumes.

## Install for global use

The smoketest assumes `redistail` is on `$PATH`. The cleanest way is via
[`uv`](https://docs.astral.sh/uv/):

```bash
# From a release / PyPI build
uv tool install redistail

# Or from a local checkout (editable: code changes take effect immediately)
cd /path/to/02_redistail
uv tool install --force -e .
```

`uv tool install` drops a shim at `~/.local/bin/redistail`. Make sure
`~/.local/bin` is on your `$PATH` (most modern shells set this up
automatically; otherwise add `export PATH="$HOME/.local/bin:$PATH"` to
your shell rc).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `redistail: command not found` | shim not on `$PATH` | See [Install for global use](#install-for-global-use); ensure `~/.local/bin` is on `$PATH` |
| Header prints, then no events | tail started after writes; pub/sub has no replay | Restart tail first, then run traffic |
| Header prints, writes happen, still no events | `notify-keyspace-events` empty / not `KEA` | `docker exec redistail-smoke redis-cli CONFIG SET notify-keyspace-events KEA` |
| Only `set/del/expire/expired` show up | old default `--ops` allowlist | Upgrade, or pass `--ops all` explicitly |
| `Connection refused` on port 6399 | container not running | `docker ps`, then re-run §1 |
| `No such command '--no-color'` | flags placed *after* the URL | Put options *before* the URL: `redistail --no-color redis://…` |
| Heredoc JSON values aren't stored | bash quote/expansion eats them | Use the `R()` helper with single-quoted args (see §3 note) |
