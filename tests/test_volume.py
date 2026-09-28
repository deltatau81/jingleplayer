import pytest

import jingleplayer_logic as logic


@pytest.mark.parametrize(
    ("global_percent", "button_db", "expected"),
    [
        (100, 0, 1.0),
        (50, 0, 0.5),
        (0, 10, 0.0),
        (100, -10, 10 ** (-10 / 20)),
        (100, 10, 1.0),
        (50, 10, 1.0),
    ],
)
def test_calculate_effective_volume(global_percent, button_db, expected):
    assert logic.calculate_effective_volume(global_percent, button_db) == pytest.approx(expected)


def test_effective_volume_is_always_clamped():
    assert logic.calculate_effective_volume(999, 99) == 1.0
    assert logic.calculate_effective_volume(-20, 0) == 0.0


def test_global_volume_change_updates_tracked_channels_with_button_db(audio):
    first, second = audio.channel(1), audio.channel(2)
    logic.playing_channels.update({1: first, 2: second})
    logic.button_volumes[:2] = [-10, 10]

    logic.set_volume_logic(50)

    assert first.volumes[-1] == pytest.approx(0.5 * 10 ** (-10 / 20))
    assert second.volumes[-1] == 1.0
    assert logic.set_volume == 50


def test_button_volume_change_updates_only_its_running_channel(audio):
    first, second = audio.channel(1), audio.channel(2)
    logic.playing_channels.update({1: first, 2: second})

    logic.set_button_volume(1, -6)

    assert first.volumes[-1] == pytest.approx(10 ** (-6 / 20))
    assert second.volumes == []
