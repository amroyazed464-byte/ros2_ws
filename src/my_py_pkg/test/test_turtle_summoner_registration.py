"""Static registration checks for the turtle summoner node."""

from pathlib import Path


def test_turtle_summoner_console_script_is_registered():
    """The package exposes the required turtle_summoner executable."""
    setup_py = Path(__file__).resolve().parents[1] / 'setup.py'

    assert 'turtle_summoner = my_py_pkg.turtle_summoner:main' in setup_py.read_text(
        encoding='utf-8'
    )
