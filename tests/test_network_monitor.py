"""Tests for the Ethernet monitor."""

from server.network_monitor import EthernetMonitor


class _Carrier:
    """Programmable carrier reader for deterministic transition tests."""

    def __init__(self, *states):
        self.states = list(states)

    def __call__(self, iface):
        return self.states.pop(0) if self.states else None


def _monitor(states, **kw):
    events = {"connect": 0, "disconnect": 0}
    mon = EthernetMonitor(
        iface="eth0",
        on_connect=lambda: events.__setitem__("connect", events["connect"] + 1),
        on_disconnect=lambda: events.__setitem__("disconnect", events["disconnect"] + 1),
        carrier_reader=_Carrier(*states),
        **kw,
    )
    return mon, events


class TestEthernetMonitor:
    def test_first_reading_does_not_fire(self):
        """Boot with cable already in must not trigger an update."""
        mon, events = _monitor([True])
        mon.poll_once()
        assert events == {"connect": 0, "disconnect": 0}
        assert mon.state is True

    def test_connect_transition_fires_once(self):
        mon, events = _monitor([False, True, True])
        mon.poll_once()  # establish False
        mon.poll_once()  # False -> True
        mon.poll_once()  # True -> True (no change)
        assert events["connect"] == 1
        assert events["disconnect"] == 0

    def test_disconnect_transition_fires(self):
        mon, events = _monitor([True, False])
        mon.poll_once()  # establish True
        mon.poll_once()  # True -> False
        assert events["disconnect"] == 1
        assert events["connect"] == 0

    def test_flapping_fires_each_edge(self):
        mon, events = _monitor([False, True, False, True])
        for _ in range(4):
            mon.poll_once()
        assert events["connect"] == 2
        assert events["disconnect"] == 1

    def test_missing_interface_is_ignored(self):
        """None readings (no such iface on a dev laptop) never fire."""
        mon, events = _monitor([None, None])
        mon.poll_once()
        mon.poll_once()
        assert events == {"connect": 0, "disconnect": 0}
        assert mon.state is None

    def test_start_stop(self):
        mon, _ = _monitor([None], poll_interval=0.05)
        mon.start()
        assert mon.is_running
        mon.stop()
        assert not mon.is_running
