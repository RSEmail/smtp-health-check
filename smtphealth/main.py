# The MIT License (MIT)
#
# Copyright (c) 2013 Ian Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
from optparse import OptionParser
import pkg_resources

from . import SmtpHealthCheck


def main():
    version = pkg_resources.require('smtp-health-check')[0].version
    description = """\
Connects to a remote SMTP server, verifying that it responds with a banner code
that indicates a healthy system (e.g. 220). Each step of the connection may be
timed. The output of this health check shows the results of the check, and the
length of time taken by each piece of the operation.
"""
    op = OptionParser(usage='%prog [options] <host>', version=version,
                      description=description)
    op.add_option('-p', '--port',
                  type='int', metavar='NUM', default=25,
                  help='The port to connect to, default %default.')
    op.add_option('-s', '--ssl',
                  action='store_true', default=False,
                  help='Initiate an SSL handshake before getting the banner.')
    op.add_option('-d', '--dns-timeout',
                  type='int', metavar='SEC', default=10,
                  help='The DNS lookup failure timeout, default %default.')
    op.add_option('-c', '--connect-timeout',
                  type='int', metavar='SEC', default=10,
                  help='The connection failure timeout, default %default.')
    op.add_option('-e', '--ssl-timeout',
                  type='int', metavar='SEC', default=10,
                  help='The SSL handshake failure timeout, default %default.')
    op.add_option('-b', '--banner-timeout',
                  type='int', metavar='SEC', default=10,
                  help='The banner failure timeout, default %default.')
    options, extra = op.parse_args()

    if len(extra) < 1:
        op.error('At least one host must be provided.')

    check = SmtpHealthCheck(dns_timeout=options.dns_timeout,
                            connect_timeout=options.connect_timeout,
                            ssl_timeout=options.ssl_timeout,
                            banner_timeout=options.banner_timeout)
    for host in extra:
        check.run(host, options.port, options.ssl)
        return check.output(sys.stdout)


# vim:et:sts=4:sw=4:ts=4
