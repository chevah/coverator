all: build

develop: env
	@build/bin/pip install -Ue '.[dev]'

clean:
	rm -rf build

env:
	@if [ ! -d "build" ]; then virtualenv build; fi
	mkdir build/coverage-data

build: env
	@build/bin/pip install .

lint: develop
	@build/bin/pyflakes coverator/
	@build/bin/pycodestyle coverator/

test: lint
	@build/bin/python setup.py test

test_with_coverage: lint
	@build/bin/nosetests --with-coverage --cover-package=coverator --cover-tests
