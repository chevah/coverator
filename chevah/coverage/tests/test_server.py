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
        """
        Create a temp dir and file for testing uploads.
        """
        BaseTestCase.setUp(self)
        self.data = 'Some test data.'
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

    def test_post(self):
        request = Request(
            'POST',
            url='http://test/',
            files={'file': open(os.path.join(self.tempdir, 'test'))},
            data={'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0'},
            )
        prepared_request = request.prepare()

        response = self.request(
            '/',
            method='POST',
            headers=prepared_request.headers,
            body=prepared_request.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')

        uploaded_path = os.path.join(
            self.tempdir,
            'commit',
            '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
            'coverage.manual',
            )

        self.assertTrue(os.path.exists(uploaded_path))
        self.assertEquals('Some test data.', open(uploaded_path).read())

    def test_post_branch(self):
        request = Request(
            'POST',
            url='http://test/',
            files={'file': open(os.path.join(self.tempdir, 'test'))},
            data={
                'branch': 'test-branch',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )
        prepared_request = request.prepare()

        response = self.request(
            '/',
            method='POST',
            headers=prepared_request.headers,
            body=prepared_request.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')

        branch_path = os.path.join(self.tempdir, 'branch', 'test-branch')
        commit_path = os.path.join(
            self.tempdir,
            'commit',
            '0f3adff9d8f6a72c919822b8cde073a9e20505e0')

        self.assertTrue(os.path.islink(branch_path))
        self.assertEqual(commit_path, os.path.realpath(branch_path))

    def test_post_pr(self):
        request = Request(
            'POST',
            url='http://test/',
            files={'file': open(os.path.join(self.tempdir, 'test'))},
            data={
                'pr': '4242',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )
        prepared_request = request.prepare()

        response = self.request(
            '/',
            method='POST',
            headers=prepared_request.headers,
            body=prepared_request.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')

        pr_path = os.path.join(self.tempdir, 'pr', '4242')
        commit_path = os.path.join(
            self.tempdir,
            'commit',
            '0f3adff9d8f6a72c919822b8cde073a9e20505e0')

        self.assertTrue(os.path.islink(pr_path))
        self.assertEqual(commit_path, os.path.realpath(pr_path))

    def test_post_slave(self):
        request = Request(
            'POST',
            url='http://test/',
            files={'file': open(os.path.join(self.tempdir, 'test'))},
            data={
                'slave': 'buildslave-test',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )
        prepared_request = request.prepare()

        response = self.request(
            '/',
            method='POST',
            headers=prepared_request.headers,
            body=prepared_request.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')
        self.assertTrue(os.path.exists(
            os.path.join(
                self.tempdir,
                'commit',
                '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                'coverage.buildslave-test')))

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
