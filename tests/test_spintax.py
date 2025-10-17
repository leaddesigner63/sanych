from tgac.api.utils.spintax import spin


def test_spin_returns_option():
    text = spin("Hello {world|earth}")
    assert text in {"Hello world", "Hello earth"}
