from setuptools import setup

package_name = 'striper_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=[],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', [
            'launch/striper.launch.py',
            'launch/simulation.launch.py',
        ]),
        ('share/' + package_name + '/config', [
            'config/ekf_local.yaml',
            'config/ekf_global.yaml',
            'config/nav2_params.yaml',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='striper-dev',
    maintainer_email='dev@striper.local',
    description='Launch files and configuration for the Striper robot',
    license='MIT',
)
