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
        Create a temp dir for testing uploads.
        """
        BaseTestCase.setUp(self)
        self.cwd = os.getcwd()
        basetempdir = tempfile.gettempdir()
        self.tempdir = tempfile.mkdtemp(dir=basetempdir)
        self.request_handler.PATH = self.tempdir
        self.request_handler.MINIMUM_NUMBER_OF_COVERAGE_FILES = 2
        self.datadir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'data')

    def tearDown(self):
        try:
            shutil.rmtree(self.tempdir)
        except OSError:
            pass
        finally:
            BaseTestCase.tearDown(self)

    def request(self, path='/', method='POST', data={}, files={}):
        """
        Builds a request and returns the response.
        """
        req = Request(
            method,
            url='http://test%s' % path,
            data=data,
            files=files)

        prepared_request = req.prepare()

        return BaseTestCase.request(
            self,
            path,
            method=method,
            headers=prepared_request.headers,
            body=prepared_request.body)

    def test_post(self):
        """
        Will receive a file and save it using the commit SHA for the file path.
        """
        response = self.request(
            files={'file': open(os.path.join(self.datadir, 'coverage_0'))},
            data={'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0'},
            )

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
        self.assertEquals(
            open(os.path.join(self.datadir, 'coverage_0')).read(),
            open(uploaded_path).read())

    def test_post_branch(self):
        """
        Will create a symlink for the branch.
        """
        response = self.request(
            files={'file': open(os.path.join(self.datadir, 'coverage_0'))},
            data={
                'branch': 'test-branch',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )

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
        """
        Will create a symlink for the Pull Request ID.
        """
        response = self.request(
            files={'file': open(os.path.join(self.datadir, 'coverage_0'))},
            data={
                'pr': '4242',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )

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
        """
        Will use the slave name as the file sufix.
        """
        response = self.request(
            files={'file': open(os.path.join(self.datadir, 'coverage_0'))},
            data={
                'slave': 'buildslave-test',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')
        self.assertTrue(os.path.exists(
            os.path.join(
                self.tempdir,
                'commit',
                '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                'coverage.buildslave-test')))

    def test_post_pr_branch_update_symlinks(self):
        """
        Will update the branch and PR links with a new commit SHA.
        """
        response = self.request(
            files={'file': open(os.path.join(self.datadir, 'coverage_0'))},
            data={
                'branch': 'branch1',
                'pr': '4242',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )

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

        response = self.request(
            files={'file': open(os.path.join(self.datadir, 'coverage_0'))},
            data={
                'branch': 'branch1',
                'pr': '4242',
                'commit': 'a95c77e348129f99837603bc1354ceef32a20e4e',
                },
            )

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')

        pr_path = os.path.join(self.tempdir, 'pr', '4242')
        commit_path = os.path.join(
            self.tempdir,
            'commit',
            'a95c77e348129f99837603bc1354ceef32a20e4e')

        self.assertTrue(os.path.islink(pr_path))
        self.assertEqual(commit_path, os.path.realpath(pr_path))

    def test_post_combine_after_minimum_files(self):
        """
        Will combine the coverage data files and generate an HTML report
        after a minimum number of files from different slaves have been
        uploaded.
        """
        for i, slave in enumerate(['slave1', 'slave2', 'slave3']):
            response = self.request(
                files={'file': open(os.path.join(
                    self.datadir,
                    'coverage_%d' % i))},
                data={
                    'slave': slave,
                    'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                    },
                )

            self.assertEqual(response.status, 200)
            slave_path = os.path.join(
                    self.tempdir,
                    'commit',
                    '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                    'coverage.%s' % slave)

            self.assertTrue(os.path.exists(slave_path))

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
