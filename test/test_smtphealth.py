
import time
import socket
import ssl
from cStringIO import StringIO
from collections import OrderedDict

from mox import MoxTestBase, IsA, IgnoreArg

from smtphealth import Timeout, SmtpHealthCheck, DNSError, BannerSyntaxError, BannerError


class TestTimeout(MoxTestBase):

    def test_success(self):
        with Timeout(1) as t:
            time.sleep(0.1)
        self.assertGreater(t.elapsed, 0.0)
        self.assertLess(t.elapsed, 1.0)

    def test_failure(self):
        with self.assertRaises(Timeout):
            with Timeout(1):
                time.sleep(2.0)


class TestSmtpHealthCheck(MoxTestBase):

    def test_constructor(self):
        check = SmtpHealthCheck()
        self.assertEquals({'Status': 'CRITICAL'}, check.results)

    def test_lookup(self):
        check = SmtpHealthCheck()
        self.mox.StubOutWithMock(socket, 'getaddrinfo')
        socket.getaddrinfo('test', 13, socket.AF_INET, socket.SOCK_STREAM)
        self.mox.ReplayAll()
        check._lookup('test', 13)
        self.assertIn('Dns-Elapsed', check.results)

    def test_connect(self):
        check = SmtpHealthCheck()
        self.mox.StubOutWithMock(socket, 'socket')
        sock = self.mox.CreateMockAnything()
        socket.socket(1, 2, 3).AndReturn(sock)
        sock.connect(('test', 13))
        self.mox.ReplayAll()
        check._connect([(1, 2, 3, '', ('test', 13))])
        self.assertIn('Connect-Elapsed', check.results)

    def test_connect_bad_dns(self):
        check = SmtpHealthCheck()
        with self.assertRaises(DNSError):
            check._connect([])

    def test_wrap_ssl(self):
        check = SmtpHealthCheck()
        check.sock = 13
        ssl_sock = self.mox.CreateMock(ssl.SSLSocket)
        self.mox.StubOutWithMock(ssl, 'wrap_socket')
        ssl.wrap_socket(13).AndReturn(ssl_sock)
        ssl_sock.do_handshake()
        self.mox.ReplayAll()
        check._wrap_ssl()
        self.assertEqual(ssl_sock, check.sock)

    def test_get_banner(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMockAnything()
        check.sock.recv(IsA(int)).AndReturn('220 Ok\r\n')
        self.mox.ReplayAll()
        banner = check._get_banner()
        self.assertIn('Banner-Elapsed', check.results)
        self.assertEqual('220 Ok\r\n', banner)

    def test_get_banner_multiline(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMockAnything()
        check.sock.recv(IsA(int)).AndReturn('220-Part One\r\n')
        self.mox.ReplayAll()
        banner = check._get_banner()
        self.assertIn('Banner-Elapsed', check.results)
        self.assertEqual('220-Part One\r\n', banner)

    def test_get_banner_slow(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMockAnything()
        check.sock.recv(IsA(int)).AndReturn('2')
        check.sock.recv(IsA(int)).AndReturn('2')
        check.sock.recv(IsA(int)).AndReturn('0')
        check.sock.recv(IsA(int)).AndReturn(' ')
        check.sock.recv(IsA(int)).AndReturn('O')
        check.sock.recv(IsA(int)).AndReturn('k')
        check.sock.recv(IsA(int)).AndReturn('\r')
        check.sock.recv(IsA(int)).AndReturn('\n')
        self.mox.ReplayAll()
        banner = check._get_banner()
        self.assertIn('Banner-Elapsed', check.results)
        self.assertEqual('220 Ok\r\n', banner)

    def test_get_banner_long(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMockAnything()
        check.sock.recv(IsA(int)).AndReturn('a'*5120)
        check.sock.recv(IsA(int)).AndReturn('a'*5120)
        check.sock.recv(IsA(int)).AndReturn('a')
        self.mox.ReplayAll()
        with self.assertRaises(BannerError):
            check._get_banner()

    def test_check_banner(self):
        check = SmtpHealthCheck()
        check._check_banner('220 Ok\r\n')
        self.assertEqual('220', check.results['Banner-Code'])
        self.assertEqual('Ok', check.results['Banner-Message'])
        self.assertEqual('OK', check.results['Status'])

    def test_check_banner_invalid(self):
        check = SmtpHealthCheck()
        with self.assertRaises(BannerSyntaxError):
            check._check_banner('asdf\r\n')
        self.assertEquals('CRITICAL', check.results['Status'])

    def test_check_banner_failure(self):
        check = SmtpHealthCheck()
        with self.assertRaises(BannerError):
            check._check_banner('520 No!\r\n')
        self.assertEquals('CRITICAL', check.results['Status'])

    def test_close(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMock(socket.socket)
        check.sock.close()
        check.sock.close().AndRaise(socket.error)
        self.mox.ReplayAll()
        check._close(False)
        check._close(False)

    def test_close_none(self):
        check = SmtpHealthCheck()
        self.mox.ReplayAll()
        check._close(False)

    def test_close_ssl(self):
        check = SmtpHealthCheck()
        orig_sock = self.mox.CreateMock(socket.socket)
        check.sock = self.mox.CreateMock(ssl.SSLSocket)
        check.sock.unwrap().AndReturn(orig_sock)
        orig_sock.close()
        self.mox.ReplayAll()
        check._close(True)

    def test_close_ssl_exception(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMock(ssl.SSLSocket)
        check.sock.unwrap().AndRaise(ssl.SSLError)
        check.sock.close()
        self.mox.ReplayAll()
        check._close(True)

    def test_run(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(check, '_lookup')
        self.mox.StubOutWithMock(check, '_connect')
        self.mox.StubOutWithMock(check, '_get_banner')
        self.mox.StubOutWithMock(check, '_check_banner')
        check._lookup('test', 13).AndReturn('beep')
        check._connect('beep')
        check._get_banner().AndReturn('beep beep')
        check._check_banner('beep beep')
        check.sock.close()
        self.mox.ReplayAll()
        check.run('test', 13)

    def test_run_exception(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(check, '_lookup')
        self.mox.StubOutWithMock(check, '_connect')
        self.mox.StubOutWithMock(check, '_get_banner')
        self.mox.StubOutWithMock(check, '_check_banner')
        check._lookup('test', 13).AndReturn('beep')
        check._connect('beep').AndRaise(Exception('test test'))
        check.sock.close()
        self.mox.ReplayAll()
        check.run('test', 13)
        self.assertEqual('Exception', check.results['Exception-Type'])
        self.assertEqual('test test', check.results['Exception-Value'])

    def test_run_ssl(self):
        check = SmtpHealthCheck()
        check.sock = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(check, '_lookup')
        self.mox.StubOutWithMock(check, '_connect')
        self.mox.StubOutWithMock(check, '_wrap_ssl')
        self.mox.StubOutWithMock(check, '_get_banner')
        self.mox.StubOutWithMock(check, '_check_banner')
        check._lookup('test', 13).AndReturn('beep')
        check._connect('beep')
        check._wrap_ssl()
        check._get_banner().AndReturn('beep beep')
        check._check_banner('beep beep')
        check.sock.unwrap().AndReturn(check.sock)
        check.sock.close()
        self.mox.ReplayAll()
        check.run('test', 13, with_ssl=True)

    def test_check_output(self):
        check = SmtpHealthCheck()
        check.results = OrderedDict([('Status', 'OK'),
                                     ('TestFloat', 1.004),
                                     ('TestInt', 10),
                                     ('TestNone', None)])
        f = StringIO()
        self.assertEqual(0, check.output(f))
        self.assertEqual("""\
Status: OK
TestFloat: 1.00400
TestInt: 10
TestNone: 
""", f.getvalue())

    def test_check_output_critical(self):
        check = SmtpHealthCheck()
        check.results = OrderedDict([('Status', 'CRITICAL')])
        f = StringIO()
        self.assertEqual(1, check.output(f))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
