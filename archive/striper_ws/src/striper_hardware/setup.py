import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'striper_hardware'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='striper',
    maintainer_email='striper@todo.com',
    description='Hardware driver nodes for the striper line-painting robot',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'paint_valve = striper_hardware.paint_valve_node:main',
            'motor_driver = striper_hardware.motor_driver_node:main',
            'imu_node = striper_hardware.imu_node:main',
            'gps_node = striper_hardware.gps_node:main',
            'ntrip_client = striper_hardware.ntrip_client_node:main',
        ],
    },
)
