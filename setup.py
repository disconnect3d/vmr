from setuptools import setup, find_packages

setup(
    name='vmr',
    description='vmr',
    url='https://github.com/disconnect3d/vmr',
    author='disconnect3d',
    version='0.1.0',
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=['docopt'],
    entry_points={
        'console_scripts': [
            'vmr = vmr.__main__:main'
        ]
    }
)

