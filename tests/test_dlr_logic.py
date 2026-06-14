"""Tests for fake_smsc DLR accept/reject gating.

Core rule under test: a submit_sm whose DESTINATION (our virtual number) has an
active activation (Redis key `dlr:block:{number}`) gets a DELIVRD DLR; otherwise
REJECTD. On a Redis error the harness fails open (DELIVRD).
"""
import asyncio
import struct
import re

import fake_smsc
from fake_smsc import (
    SMPPSession,
    normalize_msisdn,
    BIND_TRANSCEIVER,
    BIND_TRANSCEIVER_RESP,
    SUBMIT_SM,
    SUBMIT_SM_RESP,
    DELIVER_SM,
    DELIVER_SM_RESP,
)


class FakeRedis:
    """Minimal stand-in for the async redis client."""

    def __init__(self, store=None, raise_error=False):
        self.store = store or {}
        self.raise_error = raise_error

    async def get(self, key):
        if self.raise_error:
            raise ConnectionError("redis down")
        return self.store.get(key)


def _cstring(s):
    if isinstance(s, str):
        s = s.encode("latin-1")
    return s + b"\x00"


def _build_bind():
    body = _cstring("test") + _cstring("test") + _cstring("")
    body += struct.pack("BBB", 0x34, 0, 0) + _cstring("")
    return struct.pack(">IIII", 16 + len(body), BIND_TRANSCEIVER, 0, 1) + body


def _build_submit_sm(source, dest, message, registered_delivery=1, seq=2):
    body = b""
    body += _cstring("")                      # service_type
    body += struct.pack("BB", 0, 0)           # source ton/npi
    body += _cstring(source)
    body += struct.pack("BB", 1, 1)           # dest ton/npi
    body += _cstring(dest)
    body += struct.pack("BBB", 0, 0, 0)       # esm_class, protocol_id, priority
    body += _cstring("")                      # schedule_delivery_time
    body += _cstring("")                      # validity_period
    body += struct.pack(
        "BBBBB", registered_delivery, 0, 0, 0, len(message)
    )
    body += message.encode("latin-1")
    return struct.pack(">IIII", 16 + len(body), SUBMIT_SM, 0, seq) + body


async def _read_pdu(reader):
    header = await reader.readexactly(16)
    length, cmd, status, seq = struct.unpack(">IIII", header)
    body = await reader.readexactly(length - 16) if length > 16 else b""
    return cmd, status, seq, body


async def _run_submit_scenario(store=None, raise_error=False, registered_delivery=1,
                               source="NETFLIX", dest="593996844442", timeout=2.0):
    """Drive a real SMPPSession over a socket; return the DLR stat string or None."""
    fake_smsc.rc_client = FakeRedis(store=store, raise_error=raise_error)

    server = await asyncio.start_server(
        lambda r, w: SMPPSession(r, w, dlr_delay=0).handle(),
        "127.0.0.1", 0,
    )
    port = server.sockets[0].getsockname()[1]

    async with server:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            # bind
            writer.write(_build_bind())
            await writer.drain()
            cmd, _, _, _ = await _read_pdu(reader)
            assert cmd == BIND_TRANSCEIVER_RESP

            # submit_sm
            writer.write(_build_submit_sm(source, dest, "hi", registered_delivery))
            await writer.drain()
            cmd, _, _, _ = await _read_pdu(reader)
            assert cmd == SUBMIT_SM_RESP

            # DLR (deliver_sm) — may not arrive if registered_delivery=0
            try:
                cmd, _, seq, body = await asyncio.wait_for(_read_pdu(reader), timeout)
            except asyncio.TimeoutError:
                return None
            assert cmd == DELIVER_SM
            # ack it
            writer.write(struct.pack(">IIII", 16, DELIVER_SM_RESP, 0, seq))
            await writer.drain()

            text = body.decode("latin-1")
            m = re.search(r"stat:(\w+)", text)
            return m.group(1) if m else None
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# normalize_msisdn

def test_normalize_strips_plus_and_whitespace():
    assert normalize_msisdn("+593996844442") == "593996844442"
    assert normalize_msisdn(" 79156537788 ") == "79156537788"
    assert normalize_msisdn("79156537788") == "79156537788"
    assert normalize_msisdn(None) is None


# --------------------------------------------------------------------------- #
# accept / reject gating (the core fix)

def test_accept_when_destination_has_active_activation():
    stat = asyncio.run(_run_submit_scenario(
        store={"dlr:block:593996844442": b"1"}, dest="593996844442"))
    assert stat == "DELIVRD"


def test_reject_when_no_activation():
    stat = asyncio.run(_run_submit_scenario(store={}, dest="593996844442"))
    assert stat == "REJECTD"


def test_gating_keys_on_destination_not_source():
    # Sender name present as a key must NOT cause acceptance — only the
    # destination number matters. This is the exact bug being fixed.
    stat = asyncio.run(_run_submit_scenario(
        store={"dlr:block:NETFLIX": b"1"}, source="NETFLIX", dest="593996844442"))
    assert stat == "REJECTD"


def test_fail_open_on_redis_error():
    stat = asyncio.run(_run_submit_scenario(raise_error=True, dest="593996844442"))
    assert stat == "DELIVRD"


def test_plus_prefixed_destination_matches_digit_key():
    stat = asyncio.run(_run_submit_scenario(
        store={"dlr:block:593996844442": b"1"}, dest="+593996844442"))
    assert stat == "DELIVRD"


def test_no_dlr_when_not_requested():
    stat = asyncio.run(_run_submit_scenario(
        store={"dlr:block:593996844442": b"1"}, registered_delivery=0))
    assert stat is None
