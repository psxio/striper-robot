import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'striper_simulation'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='striper',
    maintainer_email='striper@todo.com',
    description='Simulation nodes and worlds for the striper line-painting robot',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'fake_gps = striper_simulation.fake_gps_node:main',
            'paint_visualizer = striper_simulation.paint_visualizer_node:main',
        ],
    },
)
