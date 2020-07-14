from nebuloch.mods import qualify_range, range_default_value


def test_qualify_range_excl():
    assert qualify_range(1, '!0')
    assert not qualify_range(0, '!0')
    assert not qualify_range(1, '!1')
    assert qualify_range(0, '!1')


def test_range_default_value_excl():
    assert range_default_value('!0') != 0
    assert range_default_value('!1') != 1
    assert range_default_value('!-1') != -1
