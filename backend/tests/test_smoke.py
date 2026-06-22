import realestate


def test_package_has_version():
    assert isinstance(realestate.__version__, str)
    assert realestate.__version__
