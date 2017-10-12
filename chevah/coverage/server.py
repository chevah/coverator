from __future__ import unicode_literals
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

import coverage

import cgi, os, posixpath, urllib

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
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })

        percentage = 0.0
        if form.has_key('file'):
            coverage_file = form['file']
            filename = coverage_file.filename
            data = coverage_file.file.read()
            slave = form.getvalue('slave')

            for key in ('branch', 'pr'):
                if form.has_key(key):
                    path = '/tmp/chevahcoverages/%s-%s' % (key, form.getvalue(key))
                    if not os.path.exists(path):
                        os.mkdir(path)
                    open(os.path.join(path, 'coverage.%s' % slave), 'wb').write(data)

                    # Maybe shouldn't call this for every uploaded file, but wait so we have some
                    # files (for each buildslave)
                    c = coverage.Coverage(data_file=os.path.join(path, 'coverage'))
                    c.combine(data_paths=[path], strict=True) 
                    c.load()
                    percentage = c.html_report(directory=path)

        response = '{result: %f}' % percentage
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
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
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


if not os.path.exists(ChevahCoverageHandler.PATH):
    os.mkdir(ChevahCoverageHandler.PATH)

server = HTTPServer(('', 8080), ChevahCoverageHandler)
#server.serve_forever()
