from __future__ import unicode_literals

import requests
import argparse
import sys


def upload_file(filepath, url, slave, commit, branch, pr):
    files = {'file': open(filepath)}
    requests.post(
        url,
        data=dict(pr=pr, commit=commit, slave=slave, branch=branch),
        files=files)


def main(*argv, **kwargs):
    parser = argparse.ArgumentParser(
        prog='chevah-coverage', add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Upload reports to a Chevah Coverage server")

    parser.add_argument(
        'url',
        default=None,
        help='URL to upload to')
    parser.add_argument(
        'coverage_file',
        default=None,
        help='Coverage.py data file')
    parser.add_argument(
        '--commit',
        default=None,
        help='Commit SHA')
    parser.add_argument(
        '--slave',
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

    if argv:
        args = parser.parse_args(argv)
    else:
        args = parser.parse_args()

    upload_file(
        args.coverage_file, args.url, args.slave,
        args.commit, args.branch, args.pr)


if __name__ == '__main__':
    main(*sys.argv[1:])
