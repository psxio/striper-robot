"""Setup for striper_pathgen — parking lot path generation library."""

from setuptools import setup, find_packages

setup(
    name="striper-pathgen",
    version="0.2.0",
    description="Path generation for autonomous line striping robots",
    packages=find_packages(),
    package_data={"": ["templates/*.json"]},
    python_requires=">=3.10",
    install_requires=[
        "ezdxf>=0.18.0",
        "svgpathtools>=1.6.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0", "matplotlib>=3.7.0"],
    },
    entry_points={
        "console_scripts": [
            "striper-pathgen=striper_pathgen.cli:main",
        ],
    },
)
