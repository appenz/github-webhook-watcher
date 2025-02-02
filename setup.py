from setuptools import setup, find_packages

setup(
    name="intra_deploy",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "svix",
    ],
    python_requires=">=3.9",
)