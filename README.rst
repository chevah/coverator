chevah-coverage
===============

The aim of this project is to provide an alternative to codecov's features.

It contains an HTTP server which receives a coverage data file and metadata
like the current revision, branch, pull request and builder, and contains also
a command line tool for uploading the coverage data file.


Development
===========

Run the tests with `make test`. This will create a virtualenv, download
all dependencies and run the tests.


Server
======

First edit the config file (`config.ini`) setting the path where all coverage
files will be stored, then run:

`build/bin/chevah-coverage-server config.ini`

Whenever you upload enough files (see the `min_buildslaves` configuration)
to the server you can see the reports by accessing `http://localhost:8080/`.

Reports are organized and aggregated by commit, branch name and
pull request ID.


Client
======

You can generate a coverage file by running:

`make test_with_coverage`

Then to upload a coverage file run the command:

`build/bin/chevah-coverage --file .coverage http://localhost:8080/`

You can specify the `commit`, the buildslave name, branch name and
pull request ID. To check all command line options run:

`./build/bin/chevah-coverage -h`
