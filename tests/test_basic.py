"""
Basic tests to verify package setup.
"""
from webhookclient import __version__

def test_version():
    """Test version is a string."""
    assert isinstance(__version__, str)
