from setuptools import find_packages, setup

package_name = 'striper_integration_tests'

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
    description='Integration and end-to-end tests for the striper robot',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [],
    },
)
