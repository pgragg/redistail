# Changelog

All notable changes to redistail will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial project scaffold (`pyproject.toml`, package layout, CLI entrypoint stub).
- CLI flags: `[URL]`, `--db`, `--pattern`, `--exclude`, `--ops`, `--json`, `--no-color`, `--no-time`, `--verbose`, `--max-width`, `--redact`, `--with-values`, `--monitor`, `--log-file`, `--expand-all`, `--collapse-threshold`, `--config`, `--version`.
- `$REDIS_URL` env fallback and `NO_COLOR` env var support.
- Startup connection validation (PING + INFO) with friendly errors on bad / unreachable URLs (exit 2).
- Preflight check: `notify-keyspace-events` (must contain K + E) and ACL command permissions (`PSUBSCRIBE`, or `MONITOR` in `--monitor` mode). Exits 3 with a copy-pasteable fix on failure. Detects ElastiCache / Memorystore / Azure / Upstash / Redis Cloud / DigitalOcean from the hostname and links to provider-specific docs.
