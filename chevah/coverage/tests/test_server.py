# from mock import Mock

from chevah.coverage.server import ChevahCoverageHandler
from test.test_httpservers import BaseTestCase, NoLogRequestHandler
from requests import Request

import os
import tempfile
import shutil


class TestChevahCoverageHandler(BaseTestCase):
    """
    Tests for ChevahCoverageHandler.

    Following the patterns from test.test_httpservers from stdlib.
    """
    class request_handler(NoLogRequestHandler, ChevahCoverageHandler):
        pass

    def setUp(self):
        BaseTestCase.setUp(self)
        self.data = 'This is some test data'
        self.cwd = os.getcwd()
        basetempdir = tempfile.gettempdir()
        self.tempdir = tempfile.mkdtemp(dir=basetempdir)
        self.tempdir_name = os.path.basename(self.tempdir)
        temp = open(os.path.join(self.tempdir, 'test'), 'wb')
        temp.write(self.data)
        temp.close()
        self.request_handler.PATH = self.tempdir

    def tearDown(self):
        try:
            shutil.rmtree(self.tempdir)
        except OSError:
            pass
        finally:
            BaseTestCase.tearDown(self)

    def check_status_and_reason(self, response, status, data=None):
        body = response.read()
        self.assertTrue(response)
        self.assertEqual(response.status, status)
        self.assertIsNotNone(response.reason)
        if data:
            self.assertEqual(data, body)

    def test_post(self):
        request = Request(
            'POST',
            url='http://test/',
            files={'files': open(os.path.join(self.tempdir, 'test'))},
            )
        prepared_request = request.prepare()

        response = self.request(
            '/',
            method='POST',
            headers=prepared_request.headers,
            body=prepared_request.body)

        self.check_status_and_reason(response, 200, '{result: 0.00}')
        self.assertEqual(response.getheader('content-length'), '14')
        self.assertEqual(response.getheader('content-type'),
                         'application/json')

    def test_translate_path(self):
        """
        Will use the configurable class variable PATH when translating
        URL paths.
        """
        class NoRequestChevahCoverageHandler(ChevahCoverageHandler):
            PATH = '/a/generic/path'

            def __init__(self):
                pass

        sut = NoRequestChevahCoverageHandler()
        result = sut.translate_path('/test')
        self.assertEqual(u'/a/generic/path/test', result)
