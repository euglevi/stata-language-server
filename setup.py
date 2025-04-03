from setuptools import setup, find_packages

setup(
    name="stata-language-server",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pygls>=1.3.1",
    ],
    entry_points={
        "console_scripts": [
            "stata-language-server=server.__main__:main",
        ],
    },
    package_data={
        'server': ['commands.json', 'md_syntax/*.md'],
    },
    include_package_data=True,
)
