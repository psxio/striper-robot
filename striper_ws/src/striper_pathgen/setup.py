"""Setup script for the striper_pathgen package."""

from setuptools import setup, find_packages

setup(
    name="striper_pathgen",
    version="0.1.0",
    description="Path generation for autonomous parking lot line striping robots",
    author="Striper Robotics",
    license="Apache-2.0",
    packages=find_packages(),
    package_data={
        "": ["../templates/*.json"],
    },
    data_files=[
        ("share/striper_pathgen/templates", [
            "templates/standard_space.json",
            "templates/handicap_space.json",
            "templates/arrow.json",
            "templates/crosswalk.json",
        ]),
    ],
    install_requires=[],
    extras_require={
        "dxf": ["ezdxf"],
        "svg": ["svgpathtools"],
        "all": ["ezdxf", "svgpathtools"],
    },
    python_requires=">=3.10",
    zip_safe=False,
)
