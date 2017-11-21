from coverator.server import (
    CoveratorHandler,
    ReportGenerator,
    SetQueue,
    )
from test.test_httpservers import BaseTestCase, NoLogRequestHandler
from requests import Request
from unittest import TestCase

import os
import tempfile
import shutil


class TestCoveratorHandler(BaseTestCase):
    """
    Tests for CoveratorHandler.

    Following the patterns from test.test_httpservers from stdlib.
    """
    class request_handler(NoLogRequestHandler, CoveratorHandler):
        pass

    def setUp(self):
        """
        Create a temp dir for testing uploads.
        """
        BaseTestCase.setUp(self)
        basetempdir = tempfile.gettempdir()
        self.tempdir = tempfile.mkdtemp(dir=basetempdir)
        self.request_handler.PATH = self.tempdir
        self.request_handler.MINIMUM_FILES = 2
        self.datadir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'data')

    def tearDown(self):
        if self.request_handler.report_generator:
            # Stops the generator thread
            self.request_handler.report_generator.queue.put(None)
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
        Will receive a file and save it to the configured path.
        """
        response = self.request(
            files={'file': open(os.path.join(self.datadir, 'coverage_0'))},
            )

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')

        repo_path = os.path.join(self.tempdir, 'no-repository')

        uploaded_path = os.path.join(
            repo_path,
            'commit',
            'no-commit',
            'coverage.data.no-buildslave',
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

        repo_path = os.path.join(self.tempdir, 'no-repository')
        branch_path = os.path.join(repo_path, 'branch', 'test-branch')
        commit_path = os.path.join(
            repo_path,
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

        repo_path = os.path.join(self.tempdir, 'no-repository')
        pr_path = os.path.join(repo_path, 'pr', '4242')
        commit_path = os.path.join(
            repo_path,
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
                'build': 'buildslave-test',
                'commit': '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                },
            )

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('content-type'),
                         'application/json')
        self.assertTrue(os.path.exists(
            os.path.join(
                self.tempdir,
                'no-repository',
                'commit',
                '0f3adff9d8f6a72c919822b8cde073a9e20505e0',
                'coverage.data.buildslave-test')))

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

        repo_path = os.path.join(self.tempdir, 'no-repository')
        pr_path = os.path.join(repo_path, 'pr', '4242')
        commit_path = os.path.join(
            repo_path,
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

        commit_path = os.path.join(
            repo_path,
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
        # Starts the report generator thread.
        self.request_handler.report_generator = ReportGenerator()
        self.request_handler.report_generator.github_base_url = None
        self.request_handler.report_generator.start()

        # Create a fake GitHub repository
        repo_name = 'test/repo'
        repo_path = os.path.join(self.tempdir, repo_name)
        git_repo_path = os.path.join(repo_path, 'git-repo')
        os.makedirs(os.path.join(git_repo_path, 'test'))
        import git
        import copy
        os.environ.copy = lambda: copy.deepcopy(os.environ)
        r = git.Repo.init(git_repo_path)
        shutil.copy(
            os.path.join(self.datadir, 'coveragerc'),
            os.path.join(git_repo_path, '.coveragerc'))
        shutil.copy(
            os.path.join(self.datadir, 'test', 'file.py'),
            os.path.join(git_repo_path, 'test', 'file.py'))
        shutil.copy(
            os.path.join(self.datadir, 'test', '__init__.py'),
            os.path.join(git_repo_path, 'test', '__init__.py'))

        r.index.add([
            os.path.join(git_repo_path, '.coveragerc'),
            os.path.join(git_repo_path, 'test/file.py'),
            os.path.join(git_repo_path, 'test/__init__.py'),
            ])
        r.index.commit("simple commit")
        commit = r.refs['master'].commit.hexsha
        commit_path = os.path.join(repo_path, 'commit', commit)

        for i, slave in enumerate(['slave1', 'slave2', 'slave3']):
            response = self.request(
                files={'file': open(os.path.join(
                    self.datadir,
                    'coverage_%d' % i))},
                data={
                    'build': slave,
                    'repository': repo_name,
                    'commit': commit,
                    },
                )

            self.assertEqual(response.status, 200)
            slave_path = os.path.join(
                    commit_path,
                    'coverage.data.%s' % slave)
            self.assertTrue(os.path.exists(slave_path))

        # Wait for the reporter generator thread to consume the queue.
        self.request_handler.report_generator.queue.join()

        # self.assertTrue(os.path.exists(
        #     os.path.join(commit_path, 'index.html')))

    def test_translate_path(self):
        """
        Will use the configurable class variable PATH when translating
        URL paths.
        """
        class NoRequestCoveratorHandler(CoveratorHandler):
            PATH = '/a/generic/path'

            def __init__(self):
                pass

        sut = NoRequestCoveratorHandler()
        result = sut.translate_path('/test/')
        self.assertEqual(u'/a/generic/path/test/', result)


class TestSetQueue(TestCase):
    """
    Tests for SetQueue class.
    """
    def test_set_queue(self):
        """
        Will not add repeated elements to the queue.
        """
        sut = SetQueue()
        self.assertEquals(0, sut.qsize())
        sut.put('test')
        self.assertEquals(1, sut.qsize())
        sut.put('test2')
        self.assertEquals(2, sut.qsize())
        sut.put('test')
        self.assertEquals(2, sut.qsize())
