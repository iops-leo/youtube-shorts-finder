from setuptools import setup, find_packages

setup(
    name="common_utils",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "google-api-python-client",
        "pytz",
        "isodate",
        "deep-translator",
    ],
)