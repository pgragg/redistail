# redistail

**Tail Redis key changes (SET / DEL / EXPIRE / HSET / …) with color in your terminal,
via keyspace notifications.** No Lua scripts. No `KEYS *`. Read-only on your data.

```text
14:02:11  SET     session:abc123        "ttl=900, size=412"
14:02:11  EXPIRE  session:abc123        ttl: 900s
14:02:12  HSET    user:42               field=last_seen
14:02:12  DEL     session:abc123
```

> Why redistail? `redis-cli MONITOR` floods you with every command, including
> reads. `redistail` shows you *changes* — what your app, your background
> workers, and your TTL expirations are actually doing to keys, live, while
> you watch.

## 30-second quickstart

```bash
# 1. Install
uv tool install redistail            # or: pipx install redistail / pip install redistail

# 2. Make sure Redis has keyspace notifications on (one-time, see below)

# 3. Tail it
redistail redis://localhost:6379/0
```

That's it. Make a change in another window — `SET foo bar` — and watch it
scroll by.

If `$REDIS_URL` is set, you can drop the URL argument entirely:

```bash
redistail
```

## Requirements

- **Redis ≥ 6** (keyspace notifications work on 4+, but pattern subscribe
  semantics and `CLIENT NO-EVICT` are stable from 6 onwards)
- `notify-keyspace-events` configured to publish at least key-event types
  (e.g. `KEA`)
- A user with permission to `PSUBSCRIBE` and (optionally) `MONITOR`
- Python 3.11+ on the client (your laptop)

`redistail` uses Redis's built-in keyspace notifications over Pub/Sub —
**no modules or scripts to install**, which means it works against managed
Redis providers and locked-down staging boxes alike.

## Configuring Redis for keyspace notifications

If you control the server, this is a one-time change:

```bash
# Enable all key-event notifications
redis-cli CONFIG SET notify-keyspace-events KEA

# Persist across restarts (writes to redis.conf if CONFIG REWRITE is allowed)
redis-cli CONFIG REWRITE
```

The flag string is a bitmask:

| Char | Meaning |
|------|---------|
| `K`  | Keyspace events: `__keyspace@<db>__:<key>` channel |
| `E`  | Keyevent events: `__keyevent@<db>__:<event>` channel |
| `g`  | Generic commands (DEL, EXPIRE, RENAME, …) |
| `$`  | String commands |
| `l`  | List commands |
| `s`  | Set commands |
| `h`  | Hash commands |
| `z`  | Sorted-set commands |
| `t`  | Stream commands |
| `x`  | Expired events |
| `e`  | Evicted events |
| `A`  | Alias for `g$lshzxet` (everything except `m` / `n`) |

`KEA` (the redistail default expectation) means: keyspace + keyevent
channels, all command groups. Verify:

```bash
redis-cli CONFIG GET notify-keyspace-events
# 1) "notify-keyspace-events"
# 2) "AKE"   ← order of letters doesn't matter
```

`redistail` runs a preflight check on startup and prints a clear error if
notifications are disabled.

### Managed providers

| Provider          | How to enable keyspace notifications                                  |
|-------------------|-----------------------------------------------------------------------|
| **AWS ElastiCache** | Set parameter group `notify-keyspace-events = AKE`, reboot if needed. |
| **GCP Memorystore** | Set the `notify-keyspace-events` config option to `AKE`.            |
| **Azure Cache for Redis** | Use "Advanced settings" → `notify-keyspace-events = AKE`.       |
| **Upstash**       | Already on by default for paid tiers; check console for free tier.    |
| **Redis Cloud**   | Set `notify-keyspace-events = AKE` in database settings.              |
| **DigitalOcean**  | Set via the managed-database "Eviction policy & notifications" panel. |

## Common flags

```text
redistail [URL]
  --db 0,1                     # comma-separated db number include list (default: 0)
  --pattern 'session:*,user:*' # glob include list (matched against the key)
  --exclude 'cache:*'          # glob exclude list
  --ops set,del,expire         # which key-event types to show
  --json                       # one JSON object per change (pipe-friendly)
  --no-color                   # disable ANSI colors (also: NO_COLOR=1)
  --no-time                    # hide the HH:MM:SS column
  -v / --verbose               # include db number and channel on every line
  --max-width 120              # truncate long values
  --redact 'session:*,token:*' # mask values for matching keys as ***
  --with-values                # GET / HGETALL the changed key (extra round-trip)
  --monitor                    # use MONITOR instead of keyspace notifications
  --log-file changes.log       # tee plain output to a file
  --expand-all                 # don't collapse high-frequency keys
  --collapse-threshold 1000    # events-per-(op,key-prefix) before collapsing
  --config ./.redistail.toml   # config file path (auto-discovered too)
```

Run `redistail --help` for the complete list.

## Config file

`redistail` auto-discovers `./.redistail.toml` in the current directory, then
`~/.config/redistail/config.toml`. CLI flags always win over config-file values.

```toml
# .redistail.toml
url = "redis://dev:dev@localhost:6379/0"

dbs      = [0, 1]
patterns = ["session:*", "user:*", "order:*"]
exclude  = ["cache:*", "rate-limit:*"]
ops      = ["set", "del", "expire", "expired"]

json    = false
verbose = true
redact  = ["session:*", "token:*", "*:secret"]

with_values        = false
collapse_threshold = 5000
max_width          = 120
```

## Examples

```bash
# Watch only session keys, skip cache churn
redistail --pattern 'session:*' --exclude 'cache:*'

# Pipe JSON into jq
redistail --json --no-color | jq 'select(.op == "expired")'

# Tee a debug log while still watching colorized output
redistail --log-file /tmp/redistail.log

# Show what TTLs are firing in production
redistail --ops expired,evicted

# MONITOR mode — see every command (heavier, includes reads)
redistail --monitor
```

## Does this modify Redis?

**No.**

- `redistail` does not write keys.
- `redistail` does not run `KEYS`, `FLUSHDB`, or `DEBUG`.
- The only server-side interaction is `PSUBSCRIBE` on the
  `__keyspace@*__:*` and `__keyevent@*__:*` channels (or a `MONITOR`
  session if you pass `--monitor`).
- `--with-values` adds a single `GET`/`HGETALL`/`LRANGE`-style read per
  event — never a write.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `notify-keyspace-events is empty` | Notifications disabled | `CONFIG SET notify-keyspace-events AKE` |
| `NOPERM this user has no permissions to run the 'psubscribe' command` | ACL too tight | `ACL SETUSER <name> +psubscribe +subscribe ~__key*__:*` |
| No events appear, but writes are happening | Wrong db filter, or only `K` set without `E` | `CONFIG SET notify-keyspace-events KEA` |
| `MONITOR` flood | `--monitor` shows everything, including reads | Drop `--monitor` and use the default keyspace path |
| `Connection refused` | Wrong URL / Redis down | Check `redis-cli -u $REDIS_URL PING` |
| `redistail` shows no events on managed Redis | Provider hasn't enabled notifications | See managed-provider table above |
| Disk I/O spike on the server | Heavy `--with-values` against large hashes | Drop `--with-values` or narrow `--pattern` |

## How it works (one paragraph)

`redistail` opens a regular Redis connection, runs preflight checks
(`CONFIG GET notify-keyspace-events`, `CLIENT INFO`, `ACL WHOAMI`), then
opens a second pub/sub connection and `PSUBSCRIBE`s to
`__keyevent@<db>__:*` (and `__keyspace@<db>__:*` for the key payload). Each
incoming message is parsed into a typed `KeyEvent` (op, db, key, ts, and
optionally a fetched value), filtered client-side, and rendered with
`rich`. With `--monitor`, redistail uses the `MONITOR` command instead and
synthesizes events from parsed command lines. Filtering and redaction run
client-side, so they never affect what the server publishes.

## Development

```bash
git clone …
cd 02_redistail
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

pytest -m "not integration"                 # fast unit tests
REDISTAIL_TEST_URL=redis://… pytest         # also run the integration test
ruff check . && ruff format --check .
```

The integration test will, by default, spin up a Redis container via
`testcontainers`. Set `REDISTAIL_TEST_URL` to point at any Redis with
`notify-keyspace-events` enabled to skip Docker (this is what CI does).

## License

MIT.
