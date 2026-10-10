import threading
import time
from unittest.mock import MagicMock

from auspex_ingest.connectors import RateLimitedClient


class _FakeTime:
    """A clock that only moves when the client sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _client(limits: dict[str, float], fake: _FakeTime) -> tuple[RateLimitedClient, MagicMock]:
    http = MagicMock()
    http.get.return_value = MagicMock(status_code=200)
    client = RateLimitedClient(limits, _httpx_client=http, _clock=fake.clock, _sleep=fake.sleep)
    return client, http


def test_rate_limited_client_waits_for_a_token_instead_of_raising() -> None:
    fake = _FakeTime()
    client, http = _client({"api.example.com": 1.0}, fake)

    client.get("https://api.example.com/1")
    client.get("https://api.example.com/2")
    client.get("https://api.example.com/3")

    assert http.get.call_count == 3
    assert fake.slept == [1.0, 1.0]


def test_idle_time_does_not_bank_a_burst() -> None:
    fake = _FakeTime()
    client, _ = _client({"api.example.com": 4.0}, fake)

    fake.now = 60.0
    client.get("https://api.example.com/1")
    client.get("https://api.example.com/2")

    assert fake.slept == [0.25]


def test_two_connectors_on_the_same_host_share_one_bucket() -> None:
    fake = _FakeTime()
    client, _ = _client({"eutils.ncbi.nlm.nih.gov": 1.0}, fake)

    client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi")
    client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi")

    assert fake.slept == [1.0]


def test_hosts_without_a_limit_are_not_paced() -> None:
    fake = _FakeTime()
    client, http = _client({"api.example.com": 1.0}, fake)

    for _ in range(3):
        client.get("https://other.example.org/x")

    assert http.get.call_count == 3
    assert fake.slept == []


def test_rate_limited_client_never_exceeds_the_rate_across_threads() -> None:
    rate = 20.0
    sent: list[float] = []
    lock = threading.Lock()

    def record(url: str, **kwargs: object) -> MagicMock:
        with lock:
            sent.append(time.monotonic())
        return MagicMock(status_code=200)

    def slow_clock() -> float:
        # Lets other threads run mid-reservation, so unsynchronised callers would share a token.
        time.sleep(0.001)
        return time.monotonic()

    http = MagicMock()
    http.get.side_effect = record
    client = RateLimitedClient({"api.example.com": rate}, _httpx_client=http, _clock=slow_clock)

    threads = [
        threading.Thread(target=lambda: [client.get("https://api.example.com/x") for _ in range(10)])
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)

    sent.sort()
    assert len(sent) == 40
    # Any rate + 1 consecutive requests span at least a second.
    for i in range(int(rate), len(sent)):
        window = sent[i] - sent[i - int(rate)]
        assert window >= 1.0 - 0.02, f"{int(rate) + 1} requests within {window:.3f} s"
