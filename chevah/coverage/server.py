from __future__ import unicode_literals
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

import coverage
import glob
import cgi
import os
import posixpath
import urllib


class ChevahCoverageHandler(SimpleHTTPRequestHandler):
    PATH = '/tmp/chevahcoverages'

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

        percentage = 0.0

        if 'file' in form:
            if not os.path.exists(self.PATH):
                os.mkdir(self.PATH)

            for dir_name in ('commit', 'branch', 'pr'):
                if not os.path.exists(
                        os.path.join(self.PATH, dir_name)):
                    os.mkdir(os.path.join(self.PATH, dir_name))

            coverage_file = form['file']
            data = coverage_file.file.read()
            commit = form.getvalue('commit')
            slave = form.getvalue('slave', 'manual')
            path = os.path.join(self.PATH, 'commit', commit)
            if not os.path.exists(path):
                os.mkdir(path)

            open(os.path.join(path, 'coverage.%s' % slave), 'wb').write(data)

            for key in ('branch', 'pr'):
                # Check if we are setting a branch and/or a PR and update
                # the directory structure
                if key in form:
                    value = form.getvalue(key)
                    open(os.path.join(path, '.coverage_%ss' % key), 'a').write(
                        value + os.linesep)
                    link_path = os.path.join(self.PATH, '%s' % key, value)
                    if os.path.exists(link_path):
                        os.unlink(link_path)
                    os.symlink(path, link_path)

            coverage_files = glob.glob(os.path.join(path, 'coverage.*'))
            # The minimum number of files should be configurable
            if len(coverage_files) > 5:
                c = coverage.Coverage(data_file=os.path.join(path, 'coverage'))
                c.combine(data_paths=[path], strict=True)
                c.load()
                percentage = c.html_report(directory=path)

        response = '{result: %.2f}' % percentage
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


def main():
    server = HTTPServer(('', 8080), ChevahCoverageHandler)
    server.serve_forever()

if __name__ == '__main__':
    main()
