from types import SimpleNamespace

from backend.ratelimit import client_ip


def _req(xff=None, host="10.0.0.5"):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_forged_leftmost_entry_is_ignored():
    # Attacker sends "X-Forwarded-For: 1.2.3.4"; the proxy appends the real IP.
    assert client_ip(_req("1.2.3.4, 203.0.113.9")) == "203.0.113.9"


def test_rotating_forged_values_map_to_same_ip():
    ips = {client_ip(_req(f"9.9.9.{i}, 203.0.113.9")) for i in range(20)}
    assert ips == {"203.0.113.9"}


def test_no_header_uses_socket_peer():
    assert client_ip(_req()) == "10.0.0.5"


def test_upstash_redis_url_is_upgraded_to_tls():
    from backend.config import Settings
    s = Settings(redis_url=' redis://default:pw@eu1-abc.upstash.io:6379 ')
    assert s.redis_connection_url == "rediss://default:pw@eu1-abc.upstash.io:6379"
    assert Settings(redis_url="redis://redis:6379").redis_connection_url == "redis://redis:6379"
    assert Settings(redis_url="rediss://default:pw@x.upstash.io:6379").redis_connection_url.startswith("rediss://")
