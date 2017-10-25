from __future__ import unicode_literals
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from ConfigParser import SafeConfigParser
from Queue import Queue
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


class ChevahCoverageHandler(SimpleHTTPRequestHandler):
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

            repository = form.getvalue('repository', 'no-repository')
            repository_path = os.path.join(self.PATH, repository)

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

            open(os.path.join(path, 'coverage.%s' % build), 'wb').write(
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

            coverage_files = glob.glob(os.path.join(path, 'coverage.*'))
            if len(coverage_files) > self.MINIMUM_FILES:
                self.report_generator.queue.put(path)

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
    def __init__(self):
        self.queue = Queue()
        super(ReportGenerator, self).__init__()

    def run(self):
        """
        Combine coverage data files and generate HTML reports.
        """
        while True:
            path = self.queue.get()
            if path is None:
                break
            # The coverage API will delete the coverage data files when
            # combining them. We don't want that, so let's copy to a
            # temporary dir first.
            tempdir = tempfile.mkdtemp(dir=tempfile.gettempdir())
            coverage_files = glob.glob(os.path.join(path, 'coverage.*'))
            for coverage_file in coverage_files:
                shutil.copy(coverage_file, tempdir)

            c = coverage.Coverage(data_file=os.path.join(path, 'coverage'))
            c.combine(data_paths=[path], strict=True)
            c.load()

            for coverage_file in coverage_files:
                shutil.copy(
                    os.path.join(tempdir, os.path.basename(coverage_file)),
                    os.path.dirname(coverage_file))
            shutil.rmtree(tempdir)
            c.html_report(directory=path)
            self.queue.task_done()


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(
        prog='chevah-coverage-server', add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Aggregates coverage data files and serves HTML report")

    parser.add_argument(
        'config',
        default=None,
        help='Path to the configuration file')

    args = parser.parse_args(sys.argv[1:])

    config = SafeConfigParser()
    config.read(args.config)

    ChevahCoverageHandler.PATH = config.get('server', 'path')
    ChevahCoverageHandler.MINIMUM_FILES = config.getint(
        'server', 'min_buildslaves')
    ChevahCoverageHandler.report_generator = ReportGenerator()
    ChevahCoverageHandler.report_generator.start()

    server = HTTPServer(
        ('', config.getint('server', 'port')),
        ChevahCoverageHandler)

    try:
        server.serve_forever()
    finally:
        # Stops the report generator thread
        ChevahCoverageHandler.report_generator.queue.put(None)


if __name__ == '__main__':  # pragma: no cover
    main()
