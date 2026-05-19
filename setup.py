from setuptools import setup, find_packages

setup(
    name="akaion-runner",
    version="0.1.0",
    description="Local-first second brain — markdown vault, SQLite index, optional one-way push to an Akaion-compatible backend.",
    long_description=(open("README.md").read() if __import__("os").path.exists("README.md") else ""),
    long_description_content_type="text/markdown",
    author="Akaion",
    author_email="dev@akaion.com",
    url="https://github.com/akaion/akaion-runner",
    license="Apache-2.0",
    packages=find_packages(),
    install_requires=[
        "typer[all]>=0.12.3",
        "pydantic>=2.7.1",
        "pydantic-settings>=2.2.1",
        "python-dotenv>=1.0.1",
        "httpx>=0.27.0",
        "aiohttp>=3.9.5",
        "websockets>=12.0",
        "openai>=1.30.1",
        "anthropic>=0.25.7",
        "google-generativeai>=0.5.4",
        "PyYAML>=6.0.1",
        "rich>=13.7.1",
        "click>=8.1.7",
        "inquirer>=3.2.4",
        "watchdog>=4.0.0",
        "psutil>=5.9.8",
        "PyJWT>=2.8.0",
        "cryptography>=42.0.7",
        "loguru>=0.7.2",
    ],
    extras_require={
        "dev": [
            "pytest>=8.2.0",
            "pytest-asyncio>=0.23.6",
            "pytest-cov>=5.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "akaion=runner.cli:app",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
)
