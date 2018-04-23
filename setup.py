from setuptools import Command, find_packages, setup
import os

VERSION = '0.1.4'


class PublishCommand(Command):
    """
    Publish the source distribution to private Chevah PyPi server.
    """

    description = "Upload to Chevah private repo"
    user_options = []

    def initialize_options(self):
        self.cwd = None

    def finalize_options(self):
        self.cwd = os.getcwd()

    def run(self):
        assert os.getcwd() == self.cwd, (
            'Must be in package root: %s' % self.cwd)
        self.run_command('bdist_wheel')
        # Upload package to Chevah PyPi server.
        upload_command = self.distribution.get_command_obj('upload')
        upload_command.repository = u'chevah'
        self.run_command('upload')


distribution = setup(
    name='coverator',
    version=VERSION,
    maintainer='Adi Roiban',
    maintainer_email='adi.roiban@chevah.com',
    license='MIT',
    platforms='any',
    description=(
        'Tool for aggregating and publishing coverage reports.'
        ),
    long_description="",
    url='http://www.chevah.com',
    packages=find_packages('.'),
    install_requires=[
        'coverage==4.5',
        'requests==2.17.3',
        'codecov==2.0.3',
        'diff-cover==0.9.11',
        'GitPython==1.0.1',
        'pygithub==1.34',
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
            'coverator-server = coverator.server:main',
            'coverator-publish = coverator.client:main',
            ],
        },
    test_suite = 'coverator.tests',
    cmdclass={
         'publish': PublishCommand,
         },
    )
