"""
Setup script for QueueCTL.
"""

from setuptools import setup, find_packages

# Try to read README.md for long description, fall back to package docstring if not found
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = __doc__

setup(
    name="queuectl",
    version="1.0.0",
    description="A CLI-based background job queue system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.7",
    install_requires=[
        "click>=8.1.0",
        "python-dateutil>=2.8.0",
        "tabulate>=0.9.0",
        "psutil>=5.9.0",
        "Flask>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "queuectl=queuectl.cli:main",
        ],
    },
)