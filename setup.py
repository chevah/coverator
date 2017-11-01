from setuptools import Command, find_packages, setup
import os

VERSION = '0.1.bgola5'


class PublishCommand(Command):
    """
    Publish the source distribution to private Chevah PyPi server.
    """

    description = "copy distributable to Chevah cache folder"
    user_options = []

    def initialize_options(self):
        self.cwd = None

    def finalize_options(self):
        self.cwd = os.getcwd()

    def run(self):
        assert os.getcwd() == self.cwd, (
            'Must be in package root: %s' % self.cwd)
        self.run_command('sdist')
        # Upload package to Chevah PyPi server.
        upload_command = self.distribution.get_command_obj('upload')
        upload_command.repository = u'chevah'
        self.run_command('upload')


distribution = setup(
    name='chevah-coverage',
    version=VERSION,
    maintainer='Adi Roiban',
    maintainer_email='adi.roiban@chevah.com',
    license='MIT',
    platforms='any',
    description="codecov.io like tool for aggregating and publishing coverage reports.",
    long_description="",
    url='http://www.chevah.com',
    namespace_packages=['chevah'],
    packages=find_packages('.'),
    install_requires=[
        'coverage==4.4.1',
        'requests==2.18.4',
        'GitPython==2.1.7',
        ],
    extras_require = {
        'dev': [
            'nose',
            'pyflakes',
            'pycodestyle',
            ],
    },
    entry_points={
        'console_scripts': [
            'chevah-coverage-server = chevah.coverage.server:main',
            'chevah-coverage = chevah.coverage.client:main',
            ],
        },
    test_suite = 'chevah.coverage.tests',
    cmdclass={
         'publish': PublishCommand,
         },
    )
