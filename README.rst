coverator
=========

The aim of this project is to provide an alternative to codecov's features.

It contains an HTTP server which receives a coverage data file and metadata
like the current revision, branch, pull request and builder, and contains also
a command line tool for uploading the coverage data file.


Development
===========

Run the tests with `make test`.
This will create a virtualenv, download all dependencies and run the tests.
Before making a release, make sure that CHANGELOG.rst is updated.


Server
======

First edit the config file (`config.ini`) setting the path where all coverage
files will be stored, then run::

  $ build/bin/coverator-server config.ini

Whenever you upload enough files (see the `min_buildslaves` configuration)
to the server you can see the reports by accessing `http://localhost:8080/`.

Reports are organized and aggregated by commit, branch name and
pull request ID.


Client
======

You can generate a coverage file by running::

  $ make test_with_coverage

Then to upload a coverage file run the command::

  $ build/bin/coverator-publish --file .coverage http://localhost:8080/

You can specify the `commit`, the buildslave name, branch name and
pull request ID. To check all command line options run::

  $ build/bin/coverator-publish -h


GitHub Token
============

See here for more info about how to get a token.
https://developer.github.com/v3/oauth_authorizations/#create-a-new-authorization

Create an OAuth App for your GitHub organization:
https://github.com/organizations/YOUR-ORG/settings/applications/new

Modify github_oauth_request.json with your App details.
If you have 2FA enabled, make sure U2F is not enabled but instead have OTP.
If you have OTP over SMS, do a request without the X-GitHub-OTP token.
Then you will receive the token and make it again.

curl https://api.github.com/authorizations \
    -X POST -d @github_oauth_request.json \
    -u YOUR-USERNAME -H 'X-GitHub-OTP: YOUR-OTP'

Then get the token from the response and save it to the config file.
