from setuptools import setup, find_packages

setup(
    name="lifesync-mcp-toolkit",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.115.0",
        "pydantic>=2.9.0",
    ],
    author="LifeSync Team",
    author_email="hello@lifesync.example.com",
    description="A toolkit for building stateful, multi-agent MCP servers with persistent memory for Alexa+",
    url="https://github.com/lifesync-team/lifesync-mcp-toolkit",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
)
