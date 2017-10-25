from __future__ import unicode_literals

import requests
import argparse
import sys


def upload_coverage(
        filepath, url, repository=None, build=None,
        commit=None, branch=None, pr=None):
    files = {'file': open(filepath)}
    requests.post(
        url,
        data=dict(
            repository=repository, pr=pr, commit=commit,
            build=build, branch=branch),
        files=files)


def main():
    parser = argparse.ArgumentParser(
        prog='chevah-coverage', add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Upload reports to a Chevah Coverage server")

    parser.add_argument(
        'url',
        default=None,
        help='URL to upload to')
    parser.add_argument(
        '--file',
        default=None,
        help='Coverage.py data file')
    parser.add_argument(
        '--repository',
        default=None,
        help='Specify the github repository (e.g. chevah/chevah-coverage)')
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

    upload_coverage(
        args.file, args.url, args.repository, args.build,
        args.commit, args.branch, args.pr)


if __name__ == '__main__':
    main()
