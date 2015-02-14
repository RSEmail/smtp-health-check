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

"""Module containing the routines for testing an SMTP server to determine its
based on its response times and banner codes.

"""

from __future__ import absolute_import

import sys
import re
import socket
import ssl
import time
import signal
import traceback


class BannerError(Exception):
    """This error encompasses any exception raised regarding the banner
    received from the SMTP server.

    """
    pass


class BannerSyntaxError(BannerError):
    """This error is thrown when the banner received from the SMTP server does
    not meet the required banner syntax according to the RFC.

    """
    pass


class DNSError(Exception):
    """This error is thrown when the given SMTP server hostname does not
    resolve to any DNS records.

    """
    pass


class Timeout(Exception):
    """This class may be used as a context manager in ``with`` statements. If
    the given number of seconds elapses, the class itself (which inherits from
    ``Exception``) is raised asynchronously using signals.

    :param seconds: The number of seconds before timeout.
    :type seconds: int
    :param err: The error string to associate with the timeout exception.
    :type err: str

    """

    def __init__(self, seconds, err=None):
        super(Timeout, self).__init__(err or 'Request timed out')
        self._seconds = seconds
        self._old = signal.SIG_DFL
        self._start = None

        #: If successful, this is the total elapsed time taken by the context.
        #: For example::
        #:
        #:     with Timeout(5) as t:
        #:         # do stuff...
        #:     print t.elapsed
        #:
        self.elapsed = None

    def _fire(self, signum, frame):
        raise self

    def __enter__(self):
        if self._seconds is not None:
            self._old = signal.signal(signal.SIGALRM, self._fire)
            signal.alarm(self._seconds)
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.elapsed = time.time() - self._start
        if self._seconds is not None:
            signal.signal(signal.SIGALRM, self._old)
            signal.alarm(0)


class SmtpHealthCheck(object):
    """This class manages the flow of checking the health of a remote SMTP
    server based on their presented banner code and message. Any DNS failures,
    timeouts, and banner errors will return a critical health status for the
    server.

    :param dns_timeout: The timeout, in seconds, to wait for a DNS lookup of
                        the SMTP server hostname.
    :type dns_timeout: int
    :param connect_timeout: The timeout, in seconds, to wait for the socket
                            connection to the SMTP server.
    :type connect_timeout: int
    :param ssl_timeout: If using SSL, the timeout, in seconds, to wait for the
                        handshake with the SMTP server to finish.
    :type ssl_timeout: int
    :param banner_timeout: The timeout, in seconds, to wait for connected
                           socket to receive a complete banner message from the
                           SMTP server.
    :type banner_timeout: int

    """

    banner_pattern = re.compile(r'^(\d{3})(?:\s+|-)(.*?)\r?\n$')

    def __init__(self, dns_timeout=None, connect_timeout=None,
                 ssl_timeout=None, banner_timeout=None):
        super(SmtpHealthCheck, self).__init__()
        self.sock = None
        self.dns_timeout = dns_timeout
        self.connect_timeout = connect_timeout
        self.ssl_timeout = ssl_timeout
        self.banner_timeout = banner_timeout
        self.results = {'Status': 'CRITICAL'}

    def _lookup(self, host, port):
        sockfam = socket.AF_INET
        socktype = socket.SOCK_STREAM
        with Timeout(self.dns_timeout, 'DNS lookup timed out.') as timer:
            ret = socket.getaddrinfo(host, port, sockfam, socktype)
        self.results['Dns-Elapsed'] = timer.elapsed
        return ret

    def _connect(self, gai):
        if len(gai) < 1:
            raise DNSError('DNS lookup returned no results.')
        with Timeout(self.connect_timeout, 'Connection timed out.') as timer:
            self.sock = socket.socket(*gai[0][0:3])
            self.sock.connect(gai[0][4])
        self.results['Connect-Elapsed'] = timer.elapsed

    def _wrap_ssl(self):
        with Timeout(self.ssl_timeout, 'SSL handshake timed out.') as timer:
            self.sock = ssl.wrap_socket(self.sock)
            self.sock.do_handshake()
        self.results['Ssl-Elapsed'] = timer.elapsed

    def _get_banner(self):
        timeout_error = 'Receiving banner timed out.'
        with Timeout(self.banner_timeout, timeout_error) as timer:
            received = ''
            while True:
                part = self.sock.recv(1024)
                received = received + part
                if received.endswith('\n'):
                    ret = received
                    break
                if len(received) > 10240:
                    msg = 'Received too much data from banner.'
                    raise BannerSyntaxError(msg)
        self.results['Banner-Elapsed'] = timer.elapsed
        return ret

    def _check_banner(self, banner):
        match = self.banner_pattern.match(banner)
        if not match:
            raise BannerSyntaxError('Invalid banner received: '+repr(banner))
        code = match.group(1)
        message = match.group(2)
        self.results['Banner-Code'] = code
        self.results['Banner-Message'] = message
        if not code.startswith('2'):
            raise BannerError('Banner reported failure code: '+code)
        self.results['Status'] = 'OK'

    def _close(self, with_ssl):
        if not self.sock:
            return
        # Exceptions are suppressed because successful disconnection is not
        # important, and errors would short-circuit the proper output of the
        # health check.
        if with_ssl:
            try:
                self.sock = self.sock.unwrap()
            except socket.error:
                pass
        try:
            self.sock.close()
        except socket.error:
            pass

    def run(self, host, port=25, with_ssl=False):
        """Executes a single health check against a remote host and port. This
        method may only be called once per object.

        :param host: The hostname or IP address of the SMTP server to check.
        :type host: str
        :param port: The port number of the SMTP server to check.
        :type port: int
        :param with_ssl: If ``True``, SSL will be initiated before attempting
                         to get the banner message.
        :type with_ssl: bool

        """
        try:
            dns_rec = self._lookup(host, port)
            self._connect(dns_rec)
            if with_ssl:
                self._wrap_ssl()
            banner = self._get_banner()
            self._check_banner(banner)
        except Exception:
            exc_type, exc_value, exc_tb = sys.exc_info()
            self.results['Exception-Type'] = str(exc_type.__name__)
            self.results['Exception-Value'] = str(exc_value)
            self.results['Exception-Traceback'] = repr(traceback.format_exc())
        finally:
            self._close(with_ssl)

    def output(self, stream):
        """Outputs the results of :meth:`.run` to the given stream. The results
        are presented similarly to HTTP headers, where each line has a key and
        value, separated by ``: ``. The ``Status`` key will always be available
        in the output.

        :param stream: The output file to write to.
        :returns: A return code that would be appropriate to return to the
                  operating system, e.g. zero means success, non-zero means
                  failure.
        :rtype: int

        """
        for key, val in self.results.items():
            if isinstance(val, basestring):
                print >> stream, '{0}: {1!s}'.format(key, val)
            elif isinstance(val, float):
                print >> stream, '{0}: {1:.5f}'.format(key, val)
            elif val is None:
                print >> stream, '{0}: '.format(key)
            else:
                print >> stream, '{0}: {1!s}'.format(key, val)
        if self.results['Status'] == 'OK':
            return 0
        else:
            return 1


# vim:et:sts=4:sw=4:ts=4
