from types import SimpleNamespace

import pytest

import jingleplayer_logic as logic


class FakeSound:
    def __init__(self, path):
        self.path = path


class FakeChannel:
    def __init__(self, number=0):
        self.number = number
        self.sound = None
        self.busy = False
        self.fadeouts = []
        self.stop_calls = 0
        self.volumes = []
        self.endevent = None

    def play(self, sound):
        self.sound = sound
        self.busy = True

    def fadeout(self, milliseconds):
        self.fadeouts.append(milliseconds)
        self.busy = False

    def stop(self):
        self.stop_calls += 1
        self.busy = False

    def set_volume(self, value):
        self.volumes.append(value)

    def get_busy(self):
        return self.busy

    def set_endevent(self, event):
        self.endevent = event


class FakeMixer:
    def __init__(self):
        self.channels = []
        self.available = []
        self.loaded_paths = []
        self.load_error = None

    def Sound(self, path):
        if self.load_error:
            raise self.load_error
        self.loaded_paths.append(path)
        return FakeSound(path)

    def find_channel(self):
        return self.available.pop(0) if self.available else None

    def get_num_channels(self):
        return len(self.channels)

    def Channel(self, index):
        return self.channels[index]


@pytest.fixture
def audio(monkeypatch):
    mixer = FakeMixer()
    events = []
    fake_pygame = SimpleNamespace(
        mixer=mixer,
        event=SimpleNamespace(get=lambda: list(events)),
        USEREVENT=1000,
        NUMEVENTS=2000,
    )
    monkeypatch.setattr(logic, "pygame", fake_pygame)
    monkeypatch.setattr(logic, "pygame_available", True)
    logic.sounds.clear()
    logic.playing_channels.clear()
    logic._playbacks_by_event.clear()
    logic._events_by_button.clear()
    logic._next_end_event = None
    logic.button_volumes = [0] * logic.DEFAULT_BUTTON_COUNT
    logic.set_volume = 100
    logic.current_jingle = None
    logic.jingle_playing = False
    return SimpleNamespace(mixer=mixer, events=events, channel=FakeChannel)
