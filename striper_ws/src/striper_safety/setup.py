from setuptools import find_packages, setup

package_name = 'striper_safety'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='striper',
    maintainer_email='striper@todo.com',
    description='Safety nodes for the striper line-painting robot',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'safety_supervisor = striper_safety.safety_supervisor_node:main',
            'obstacle_detector = striper_safety.obstacle_detector_node:main',
            'geofence = striper_safety.geofence_node:main',
            'watchdog = striper_safety.watchdog_node:main',
            'operator_override = striper_safety.operator_override_node:main',
        ],
    },
)
