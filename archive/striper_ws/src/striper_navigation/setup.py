from setuptools import find_packages, setup

package_name = 'striper_navigation'

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
    description='Navigation nodes for the striper line-painting robot',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'path_manager = striper_navigation.path_manager_node:main',
            'speed_regulator = striper_navigation.speed_regulator_node:main',
            'paint_controller = striper_navigation.paint_controller_node:main',
        ],
    },
)
