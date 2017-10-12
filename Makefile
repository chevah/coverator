all: test
	

clean:
	rm -rf build

env:
	@if [ ! -d "build" ]; then virtualenv build; fi


deps: env
	@build/bin/pip install -Ue '.[dev]'


lint:
	@build/bin/pyflakes chevah/
	@build/bin/pep8 chevah/


test: lint
	@build/bin/python setup.py test
