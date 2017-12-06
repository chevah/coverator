from __future__ import unicode_literals

import requests
import argparse
import sys


DEFAULT_URL = 'http://coverage.chevah.com:8080'


def upload_coverage(
        filepath, repository=None, build=None, commit=None,
        branch=None, pr=None, url=DEFAULT_URL, timeout=30):
    """
    Sends a POST request uploading a coverage data file to a coverator server.
    """
    files = {'file': open(filepath)}
    print('Uploading coverage data file with the following configuration:')
    print('FILE: %s' % filepath)
    print('REPOSITORY: %s' % repository)
    print('BUILDER: %s' % build)
    print('COMMIT: %s' % commit)
    print('BRANCH: %s' % branch)
    print('GITHUB_PR: %s' % pr)
    print('URL: %s' % url)
    print('TIMEOUT: %s' % timeout)

    response = requests.post(
        url,
        data=dict(
            repository=repository, pr=pr, commit=commit,
            build=build, branch=branch),
        files=files,
        timeout=timeout)
    if response.status_code != 200:
        print('Failed to upload, response code was %d.' % response.status_code)
        return response.status_code
    print('Done.')
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog='coverator-publish', add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Upload reports to a coverator server")

    parser.add_argument(
        'url',
        default=DEFAULT_URL,
        help='URL to upload to')
    parser.add_argument(
        '--file',
        default=None,
        help='Coverage.py data file')
    parser.add_argument(
        '--repository',
        default=None,
        help='Specify the github repository (e.g. chevah/coverator)')
    parser.add_argument(
        '--commit',
        default=None,
        help='Commit SHA')
    parser.add_argument(
        '--build',
        default=None,
        help='Specify a buildslave')
    parser.add_argument(
        '--pr',
        default=None,
        help='Specify a custom pr number')
    parser.add_argument(
        '--branch',
        default=None,
        help='Specify a custom branch name')

    args = parser.parse_args(sys.argv[1:])

    return upload_coverage(
        args.file, args.repository, args.build,
        args.commit, args.branch, args.pr, args.url)


if __name__ == '__main__':
    sys.exit(main())
