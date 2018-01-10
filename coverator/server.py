from __future__ import unicode_literals

from BaseHTTPServer import HTTPServer
from ConfigParser import SafeConfigParser
from git import Repo
from github import Github
from Queue import Empty
from multiprocessing import Queue, Process
from SimpleHTTPServer import SimpleHTTPRequestHandler
from subprocess import call

import argparse
import cgi
import glob
import os
import posixpath
import shutil
import sys
import tempfile
import time
import urllib


COVERAGE_DATA_PREFIX = 'coverage.data.'


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
            if not os.path.exists(self.PATH):
                self.log_message('Creating dir: %s.', self.PATH)
                os.mkdir(self.PATH)

            repo = form.getvalue('repository', None)

            if repo is None:
                repo = 'no-repository'

            repository_path = os.path.join(self.PATH, repo)

            if not os.path.exists(repository_path):
                self.log_message('Creating dir: %s.', repository_path)
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

            self.log_message('Writing coverage file: (%s,%s)', build, commit)

            f = open(os.path.join(path, '%s%s' % (
                    COVERAGE_DATA_PREFIX, build)), 'wb')
            f.write(coverage_file.read())
            f.close()

            self.log_message('Done.')

            for key in ('branch', 'pr'):
                # Check if we are setting a branch and/or a PR and update
                # the directory structure
                if key in form:
                    value = form.getvalue(key)
                    open(os.path.join(path, '.coverage_%ss' % key), 'a').write(
                        value + os.linesep)
                    link_path = os.path.join(
                        repository_path, '%s' % key, value)
                    self.log_message(
                        'Updating symlink for %s -> %s', link_path, path)
                    if os.path.exists(link_path):
                        os.unlink(link_path)
                    os.symlink(path, link_path)

            coverage_files = glob.glob(os.path.join(
                path, '%s*' % COVERAGE_DATA_PREFIX))

            if len(coverage_files) > self.MINIMUM_FILES:
                now = time.time()
                self.log_message(
                    'Adding (%s, %f) to the queue' % (commit, now))
                branch = form.getvalue('branch', None)
                pr = form.getvalue('pr', None)
                self.report_generator.queue.put(
                    (self.PATH, repo, commit, branch, pr, now))

        self.log_message('Writing response.')
        response = '{success:true}'
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header("Content-length", len(response))
        self.end_headers()
        self.wfile.write(response)
        self.log_message('Response written.')

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


class ReportGenerator(Process):
    """
    Consumer process for generating reports without blocking the HTTP server.
    """

    # This is here to help with testing
    github_base_url = 'https://github.com'

    def __init__(
            self, github_token=None, url=None, codecov_tokens={},
            time_to_wait=200):
        self.queue = Queue()
        self._to_be_generated = {}
        self._stop = False
        self._time_to_wait = time_to_wait
        self.url = url
        self.codecov_tokens = codecov_tokens
        self.github = None

        if github_token:
            self.github_base_url = 'https://%s@github.com' % github_token
            self.github = Github(github_token)

        super(ReportGenerator, self).__init__()

    weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    monthname = [None,
                 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    def log_message(self, format, *args):
        sys.stderr.write(
            "consumer_process - - [%s] %s\n" % (
                self.log_date_time_string(),
                format % args))

    def log_date_time_string(self):
        """Return the current time formatted for logging."""
        now = time.time()
        year, month, day, hh, mm, ss, x, y, z = time.localtime(now)
        s = "%02d/%3s/%04d %02d:%02d:%02d" % (
                day, self.monthname[month], year, hh, mm, ss)
        return s

    def cloneGitRepo(self, repo, path, commit):
        """
        Clone a repository `repo` from github into `path` and
        checkout the revision `commit`.
        """
        # Check if we have already cloned this repository,
        # if not, we clone it from github.
        if not os.path.exists(path):
            self.log_message(
                'Cloning git repository %s/%s to %s',
                self.github_base_url, repo, path)
            git_repo = Repo.clone_from(
                '%s/%s' % (self.github_base_url, repo), path)
        else:
            self.log_message('Checking out master branch in %s', path)
            git_repo = Repo(path)
            git_repo.head.reference = git_repo.refs['master']
            git_repo.head.reset(index=True, working_tree=True)

        self.log_message('Git pull')
        git_repo.remote().pull()

        # Checkout the commit
        self.log_message('Checking out commit: %s', commit)
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

        # status_total = 'pending'
        # status_total_msg = 'Waiting for status to be reported'
        # if coverage_total is not None:
        #     status_total = 'failure'
        #     status_total_msg = 'Coverage is %.2f%%' % coverage_total
        # github_commit.create_status(
        #         status_total,
        #         '%s/%s/commit/%s' % (
        #             self.url, repo, commit),
        #         status_total_msg,
        #         'coverator/project')

        status_diff = 'pending'
        status_diff_msg = 'Waiting for status to be reported'
        if coverage_diff is not None:
            status_diff = 'failure'
            status_diff_msg = 'Coverage diff is %.2f%%' % coverage_diff
            if coverage_diff == 100:
                status_diff = 'success'

        github_commit.create_status(
                status_diff,
                '%s/%s/commit/%s/diff-cover.html' % (
                    self.url, repo, commit),
                status_diff_msg,
                'coverator/project/diff')

    def publishToCodecov(self, token, commit, branch, pr):
        """
        Publish a XML report to codecov.io.
        """
        args = ['codecov', '--build', 'coverator',
                '--file', '../commit/%s/coverage.xml' % commit,
                '-t', token]

        if branch:
            # We know the branch name from the env.
            args.extend(['--branch', branch])

        if pr:
            # We are publishing for a PR.
            args.extend(['--pr', pr])

        call(args)

    def generateReport(self, base_path, repository, commit, branch, pr):
        """
        Combine coverage data files, generate XML report and send to
        codecov.io.
        """

        # The path to save the reports
        path = os.path.join(base_path, repository, 'commit', commit)
        git_repo_path = os.path.join(base_path, repository, 'git-repo')

        # This check is here to help with testing
        if self.github_base_url is not None:  # pragma: no cover
            # self.notifyGithub(repository, commit)
            self.cloneGitRepo(repository, git_repo_path, commit)

        # Coverage.py will delete the coverage data files when
        # combining them. We don't want that, so let's copy to a
        # temporary dir first.
        tempdir = tempfile.mkdtemp(dir=tempfile.gettempdir())
        coverage_files = glob.glob(
            os.path.join(path, '%s*' % COVERAGE_DATA_PREFIX))
        self.log_message('Copying files to %s', tempdir)
        for coverage_file in coverage_files:
            shutil.copy(coverage_file, tempdir)

        # Save actual path and move to the cloned repository
        old_path = os.getcwd()
        os.chdir(os.path.join(git_repo_path))

        try:
            self.log_message('Starting to combine coverage files...')
            combined_coverage_file = os.path.join(
                path, COVERAGE_DATA_PREFIX[:-1])
            env = os.environ.copy()
            env['COVERAGE_FILE'] = combined_coverage_file

            # FIXME:4516:
            # We call coverage combine three times, one for non-windows
            # generated files, one for windows generated files and
            # one for combine the two calls.
            args = ['coverage', 'combine']
            non_win_files = [
                    f for f in glob.glob('%s/*' % tempdir)
                    if 'win' not in f]
            if non_win_files:
                self.log_message('Combining non-windows files.')
                call(args + non_win_files, env=env)

            win_files = glob.glob('%s/*win*' % tempdir)
            if win_files:
                env['COVERAGE_FILE'] = '%s.win' % (
                    combined_coverage_file)
                self.log_message('Combining windows files.')
                call(args + win_files, env=env)

                # Manually replace the windows path for linux path
                windows_file = open(
                    '%s.win' % combined_coverage_file)
                content = windows_file.read()
                windows_file.close()
                new_content = content.replace('\\\\', '/')
                windows_file = open(
                    '%s.win' % combined_coverage_file, 'w')
                windows_file.write(new_content)
                windows_file.close()

                self.log_message(
                    'Merging windows and non-windows files.')
                env['COVERAGE_FILE'] = combined_coverage_file
                call([
                    'coverage',
                    'combine',
                    '-a',
                    '%s.win' % combined_coverage_file
                    ], env=env)

            shutil.rmtree(tempdir)

            self.log_message('Files combined, generating xml report.')
            call([
                'coverage',
                'xml',
                '-o',
                os.path.join(path, 'coverage.xml'),
                ], env=env)

            # Delete the data file after the xml file is generated.
            os.remove(combined_coverage_file)

            self.log_message(
                'XML file created at %s',
                os.path.join(path, 'coverage.xml'))

            if self.github is not None:  # pragma: no cover
                # Generate the diff-coverage report.
                from diff_cover.tool import generate_coverage_report
                from diff_cover.git_path import GitPathTool
                GitPathTool.set_cwd(os.getcwd())
                self.log_message('Generating diff-cover')
                coverage_diff = generate_coverage_report(
                    [os.path.join(path, 'coverage.xml')],
                    'master',
                    os.path.join(path, 'diff-cover.html'))
                self.log_message(
                    'Diff-cover generated, now notifying github.')
                self.notifyGithub(
                    repository, commit, None, coverage_diff)

                codecov_token = self.codecov_tokens.get(repository, None)
                if codecov_token:
                    self.log_message('Publishing to codecov.io')
                    self.publishToCodecov(
                        codecov_token, commit, branch, pr)

        finally:
            os.chdir(old_path)

    def run(self):
        """
        Main process loop.
        """
        wait = 100000

        while True:
            try:
                value = self.queue.get(True, wait)

                if value is None:
                    self.log_message('Received signal to stop.')
                    self._stop = True
                else:
                    self.log_message('New value from queue: %s', value)
                    key = "%s:%s" % (value[1], value[2])
                    self._to_be_generated[key] = value
                    wait = 1
            except Empty:
                self.log_message(
                    'Queue is empty, check reports to be generated: %s' %
                    self._to_be_generated)
                if len(self._to_be_generated) == 0:
                    if self._stop:
                        # Means there is nothing else to consume.
                        self.log_message(
                            'Nothing to consume, exiting process.')
                        break
                    wait = 100000
                    continue

                first_in_queue = min(
                    self._to_be_generated.items(), key=lambda v: v[1][-1])
                when = first_in_queue[1][-1] + self._time_to_wait

                if time.time() >= when:
                    data = self._to_be_generated.pop(
                        first_in_queue[0])

                    self.log_message('Ready to generate report for: %s', data)
                    base_path, repo, commit, branch, pr, tstamp = data
                    self.generateReport(base_path, repo, commit, branch, pr)
                    wait = 1
                else:
                    wait = when - time.time()
                    self.log_message('Wait time for next report: %f' % wait)
            except KeyboardInterrupt:
                self.log_message('Exiting consumer process.')
                break
            except Exception:
                print('Exception in consumer process:', sys.exc_info())
            finally:
                self.log_message('Queue task done.')


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

    time_to_wait = config.getint(
        'server', 'seconds_before_generate_report')

    CoveratorHandler.report_generator = ReportGenerator(
        github_token, coverator_url, codecov_tokens, time_to_wait)
    CoveratorHandler.report_generator.start()

    server = HTTPServer(
        ('', config.getint('server', 'port')),
        CoveratorHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Stops the report generator process
        CoveratorHandler.report_generator.queue.put(None)


if __name__ == '__main__':  # pragma: no cover
    main()
