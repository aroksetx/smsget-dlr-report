# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Fake SMSC for testing the SMPP side of the platform — a single-file asyncio server (`fake_smsc.py`, SMPP 3.4, stdlib only) that Jasmin (or any SMPP client) binds to. It accepts any credentials, answers `submit_sm` with a message ID, and sends a `deliver_sm` delivery receipt (`stat:DELIVRD`, always) after a configurable delay.

## Commands

```bash
python fake_smsc.py                          # 0.0.0.0:2776, 5s DLR delay
python fake_smsc.py --port 2775 --dlr-delay 0
docker compose up -d                         # image aroksetx/smsget-dlr-report, port 2776, env from .env
```

## Notes

- Knobs: `--host`, `--port`, `--dlr-delay` only. No auth, no message storage, no failure simulation — DLR status is always `DELIVRD`.
- Used as the upstream connector when testing Jasmin → RabbitMQ → `smsget-jasmin-sms-queues` end-to-end without a real carrier.
- The monitoring stack (`../monitoring/alert_rules.yml`) has a `FakeSmscRejectedRatioHigh` alert keyed to this service's metrics — check `requirements.txt`/compose env if touching metrics output.
- Docker image name (`smsget-dlr-report`) differs from the repo name; the compose service is the deployable unit.
