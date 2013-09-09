smtp-health-check
=================

Initiates an SMTP connection to a host and determines its health based on
status codes and timers.

Installation
============

From [PyPi](https://pypi.python.org/pypi):

    $ sudo pip install smtp-health-check

From source code:

    $ sudo python setup.py install


Usage
=====

See the help page with:

    $ smtp-health-check --help

Once installed, trying a single check is easy:

    $ smtp-health-check smtp.gmail.com

