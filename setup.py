from setuptools import setup, find_packages

long_description = '''
vmware-cli is a minimal wrapper for vmware's vmrun command.

It was created because I felt that `vmrun` CLI was not so convenient.
'''

setup(
    name='vmr',
    description='vmr - a better vmware cli (vmrun)',
    long_description=long_description,
    url='https://github.com/disconnect3d/vmr',
    author='disconnect3d',
    author_email='dominik.b.czarnota+vmr@gmail.com',
    keywords='vmr vmrun vmware cli',
    version='0.1.0',
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=(
        'docopt==0.6.2',
        'pydhcpdparser==0.0.9'
    ),
    entry_points={
        'console_scripts': [
            'vmr = vmr.__main__:main'
        ]
    }
)

