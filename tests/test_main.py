"""Tests for the main module."""

from ia_tests_2.main import main


def test_main(capsys: object) -> None:
    """Test that main prints 'hola mundo'."""
    main()
    captured = capsys.readouterr()
    assert captured.out.strip() == "hola mundo"
