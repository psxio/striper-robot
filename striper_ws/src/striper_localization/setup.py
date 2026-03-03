from setuptools import find_packages, setup

package_name = 'striper_localization'

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
    description='Localization nodes for the striper line-painting robot',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'odom_publisher = striper_localization.odom_publisher_node:main',
            'datum_setter = striper_localization.datum_setter_node:main',
        ],
    },
)
