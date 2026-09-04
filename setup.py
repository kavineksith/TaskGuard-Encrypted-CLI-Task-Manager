from setuptools import setup, find_packages

setup(
    name="taskguard",
    version="1.0.0",
    packages=find_packages(),
    entry_points={"console_scripts": ["taskguard=main:main"]},
    python_requires=">=3.12",
    install_requires=[
        "aiosqlite>=0.20.0",
        "cryptography>=42.0.0",
        "argon2-cffi>=23.1.0",
    ],
)
