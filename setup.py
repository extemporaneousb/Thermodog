import os, sys, glob, subprocess, textwrap, setuptools
from setuptools import Extension

version = "0.1.2"

try:
    rev = subprocess.check_output(["git", "rev-parse",
                                   "--short", "HEAD"]).decode()
    rev = rev.strip()
    version = "%s+%s" % (version, rev)
except:
    pass

setuptools.setup(
    name="thermodog",
    version=version,
    description="Laboratory Sensor Management and Alarms",
    url="https://github.com/wholebiome/ThermoDog",
    author_email="jhb@wholebiome.com",
    license="LICENSE.txt",
    install_requires=["docopt"],
    tests_require=["coverage", "flake8"],
    scripts=["bin/thermodog", "bin/gasdog"],
    packages=["thermodog"],
    platforms=["MacOS X", "Posix"]
)
