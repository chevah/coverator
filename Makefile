all: build

develop: env
	@build/bin/pip install -Ue '.[dev]'

clean:
	rm -rf build

env:
	@if [ ! -d "build" ]; then virtualenv build; fi

build: env
	@build/bin/pip install .

lint: develop
	@build/bin/pyflakes chevah/
	@build/bin/pycodestyle chevah/

test: lint
	@build/bin/python setup.py test

test_with_coverage: lint
	@build/bin/nosetests --with-coverage --cover-package=chevah --cover-tests
