from __future__ import unicode_literals

from BaseHTTPServer import HTTPServer
from ConfigParser import SafeConfigParser
from git import Repo
from github import Github
from Queue import Queue
from SimpleHTTPServer import SimpleHTTPRequestHandler
from threading import Thread

import argparse
import cgi
import coverage
import glob
import os
import posixpath
import shutil
import sys
import tempfile
import urllib


COVERAGE_DATA_PREFIX = 'coverage.data.'


class SetQueue(Queue):
    """
    Implements a queue that ignores repeated values by using a set
    to store the elements.
    """
    def _init(self, maxsize):
        """
        See: Queue.Queue
        """
        self.queue = set()

    def _put(self, item):
        """
        See: Queue.Queue
        """
        self.queue.add(item)

    def _get(self):
        """
        See: Queue.Queue
        """
        return self.queue.pop()


class CoveratorHandler(SimpleHTTPRequestHandler):
    """
    Implements an HTTPRequestHandler that will receive coverage data files,
    combine them by commit and generate HTML reports.

    The uploaded files and the generated reports are stored at PATH.
    """
    PATH = None
    MINIMUM_FILES = 6
    report_generator = None

    def do_POST(self):
        """
        Receives a report file associated to a branch and or a PR,
        combine all reports by branch and PR and generate the HTML
        report.
        """
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST',
                     'CONTENT_TYPE': self.headers['Content-Type'],
                     })

        if 'file' in form:
            if not os.path.exists(self.PATH):  # pragma: no cover
                os.mkdir(self.PATH)

            repo = form.getvalue('repository', None)

            if repo is None:
                repo = 'no-repository'

            repository_path = os.path.join(self.PATH, repo)

            if not os.path.exists(repository_path):
                os.makedirs(repository_path)

            for dir_name in ('commit', 'branch', 'pr'):
                if not os.path.exists(
                        os.path.join(repository_path, dir_name)):
                    os.mkdir(os.path.join(repository_path, dir_name))

            coverage_file = form['file'].file
            commit = form.getvalue('commit', 'no-commit')
            build = form.getvalue('build', 'no-buildslave')
            path = os.path.join(repository_path, 'commit', commit)

            if not os.path.exists(path):
                os.mkdir(path)

            open(os.path.join(path, '%s%s' % (
                    COVERAGE_DATA_PREFIX, build)), 'wb').write(
                    coverage_file.read())

            for key in ('branch', 'pr'):
                # Check if we are setting a branch and/or a PR and update
                # the directory structure
                if key in form:
                    value = form.getvalue(key)
                    open(os.path.join(path, '.coverage_%ss' % key), 'a').write(
                        value + os.linesep)
                    link_path = os.path.join(
                        repository_path, '%s' % key, value)
                    if os.path.exists(link_path):
                        os.unlink(link_path)
                    os.symlink(path, link_path)

            coverage_files = glob.glob(os.path.join(
                path, '%s*' % COVERAGE_DATA_PREFIX))
            if len(coverage_files) > self.MINIMUM_FILES:
                branch = form.getvalue('branch', None)
                pr = form.getvalue('pr', None)
                self.report_generator.queue.put(
                    (self.PATH, repo, commit, branch, pr))

        response = '{success:true}'
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header("Content-length", len(response))
        self.end_headers()
        self.wfile.write(response)

    def translate_path(self, path):
        """
        This code is copied from SimpleHTTPRequestHandler.

        We overwrite the translate_path method so we can configure
        which path we will serve instead of automatically serving the current
        directory.
        """
        # abandon query parameters
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        # Don't forget explicit trailing slash when normalizing. Issue17324
        trailing_slash = path.rstrip().endswith('/')
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)

        # We use the configurable PATH variable instead of os.getcwd()
        path = self.PATH

        for word in words:
            if os.path.dirname(word) or word in (os.curdir, os.pardir):
                # Ignore components that are not a simple file/directory name
                continue
            path = os.path.join(path, word)
        if trailing_slash:
            path += '/'
        return path


class ReportGenerator(Thread):
    """
    Consumer thread for generating reports without blocking the HTTP server.
    """

    # This is here to help with testing
    github_base_url = 'http://github.com'

    def __init__(self, github_token=None, url=None, codecov_tokens={}):
        self.queue = Queue()
        self.url = url
        self.codecov_tokens = codecov_tokens
        self.github = None
        if github_token:
            self.github = Github(github_token)
        super(ReportGenerator, self).__init__()

    def cloneGitRepo(self, repo, path, commit):
        """
        Clone a repository `repo` from github into `path` and
        checkout the revision `commit`.
        """
        # First we check if we have already cloned this repository,
        # if not, we clone it from github.
        if not os.path.exists(path):
            git_repo = Repo.clone_from(
                '%s/%s' % (self.github_base_url, repo), path)
        else:
            git_repo = Repo(path)
            git_repo.head.reference = git_repo.refs['master']
            git_repo.head.reset(index=True, working_tree=True)

        git_repo.remote().pull()

        # Checkout the commit
        git_commit = git_repo.commit(commit)
        git_repo.head.reference = git_commit
        git_repo.head.reset(index=True, working_tree=True)

    def notifyGithub(
            self, repo, commit, coverage_total=None, coverage_diff=None):
        """
        Creates a commit status on github to report the coverage results.
        """
        repo_url = repo
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
        github_commit = self.github.get_repo(
                repo_url).get_commit(commit)

        status_total = 'pending'
        status_total_msg = 'Waiting for status to be reported'

        if coverage_total is not None:
            status_total = 'failure'
            status_diff_msg = 'Coverage is %f%% <%f%%>' % (coverage_total, -10)
        github_commit.create_status(
                status_total,
                '%s/%s/commit/%s' % (
                    self.url, repo, commit),
                status_total_msg,
                'coverator/project')

        status_diff = 'pending'
        status_diff_msg = 'Waiting for status to be reported'

        if coverage_diff is not None:
            status_diff = 'failure'
            status_diff_msg = 'Coverage diff is %f%%' % coverage_diff
            if coverage_diff == 100:
                status_diff = 'success'

        github_commit.create_status(
                status_diff,
                '%s/%s/commit/%s/diff-cover.html' % (
                    self.url, repo, commit),
                status_diff_msg,
                'coverator/project/diff')

    def publishToCodecov(self, token, commit, branch, pr):
        from pkg_resources import load_entry_point as lep
        codecov_main = lep('codecov', 'console_scripts', 'codecov')

        sys.argv = [
            'codecov',
            '--build', 'coverator',
            '--file', '../commit/%s/coverage.xml' % commit,
            '-t', token,
            ]

        if branch:
            # We know the branch name from the env.
            sys.argv.extend(['--branch', branch])

        if pr:
            # We are publishing for a PR.
            sys.argv.extend(['--pr', pr])

        codecov_main()

    def run(self):
        """
        Combine coverage data files and generate HTML reports.
        """
        while True:
            try:
                value = self.queue.get()
                if value is None:
                    # Means there is nothing else to consume.
                    break

                root, repo, commit, branch, pr = value

                # The path to save the reports
                path = os.path.join(root, repo, 'commit', commit)
                git_repo_path = os.path.join(root, repo, 'git-repo')

                # This check is here to help with testing
                if self.github_base_url is not None:  # pragma: no cover
                    # self.notifyGithub(repo, commit)
                    self.cloneGitRepo(repo, git_repo_path, commit)

                old_path = os.getcwd()

                try:
                    # The coverage API will delete the coverage data files when
                    # combining them. We don't want that, so let's copy to a
                    # temporary dir first.
                    tempdir = tempfile.mkdtemp(dir=tempfile.gettempdir())
                    coverage_files = glob.glob(
                        os.path.join(path, '%s*' % COVERAGE_DATA_PREFIX))
                    for coverage_file in coverage_files:
                        shutil.copy(coverage_file, tempdir)

                    # Move to the cloned repo and prepare for the reports
                    os.chdir(os.path.join(git_repo_path))
                    c = coverage.Coverage(data_file=os.path.join(
                        path, COVERAGE_DATA_PREFIX[:-1]))
                    c.combine(data_paths=[path], strict=True)

                    # Generate aggregated XML and HTML reports.
                    c.xml_report(outfile=os.path.join(path, 'coverage.xml'))
                    c.html_report(directory=path)

                    # coverage_total = c.html_report(directory=path)

                    if self.github is not None:  # pragma: no cover
                        # # Generate also the diff-coverage report.
                        # from diff_cover.tool import generate_coverage_report
                        # from diff_cover.git_path import GitPathTool
                        # GitPathTool.set_cwd(os.getcwd())
                        # coverage_diff = generate_coverage_report(
                        #     [os.path.join(path, 'coverage.xml')],
                        #     'master',
                        #     os.path.join(path, 'diff-cover.html'))
                        # self.notifyGithub(
                        #     repo, commit, coverage_total, coverage_diff)

                        codecov_token = self.codecov_tokens.get(repo, None)
                        if codecov_token:
                            self.publishToCodecov(
                                codecov_token, commit, branch, pr)

                finally:
                    os.chdir(old_path)
                    # Restore files removed by coverage.
                    for coverage_file in coverage_files:
                        shutil.copy(
                            os.path.join(
                                tempdir, os.path.basename(coverage_file)),
                            os.path.dirname(coverage_file))
                    shutil.rmtree(tempdir)
                self.queue.task_done()
            except Exception:
                print('Exception in thread:', sys.exc_info()[0])


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(
        prog='coverator-server', add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Aggregates coverage data files and serves HTML report")

    parser.add_argument(
        'config',
        default=None,
        help='Path to the configuration file')

    args = parser.parse_args(sys.argv[1:])

    config = SafeConfigParser({'github_token': None})
    config.read(args.config)

    github_token = config.get('server', 'github_token')
    coverator_url = config.get('server', 'coverator_url')
    codecov_tokens_cfg = config.get('server', 'codecov_tokens')

    codecov_tokens = {}
    for token in codecov_tokens_cfg.split(','):
        repo, tok = token.split(':')
        codecov_tokens[repo.strip()] = tok.strip()

    path = config.get('server', 'path')

    CoveratorHandler.PATH = os.path.abspath(path)
    CoveratorHandler.MINIMUM_FILES = config.getint(
        'server', 'min_buildslaves')

    CoveratorHandler.report_generator = ReportGenerator(
        github_token, coverator_url, codecov_tokens)
    CoveratorHandler.report_generator.start()

    server = HTTPServer(
        ('', config.getint('server', 'port')),
        CoveratorHandler)

    try:
        server.serve_forever()
    finally:
        # Stops the report generator thread
        CoveratorHandler.report_generator.queue.put(None)


if __name__ == '__main__':  # pragma: no cover
    main()
