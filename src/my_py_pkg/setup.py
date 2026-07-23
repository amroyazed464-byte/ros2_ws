from setuptools import find_packages, setup

package_name = 'my_py_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jay',
    maintainer_email='jay@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'py_node = my_py_pkg.my_first_node:main',
            'robot_news_station = my_py_pkg.robot_news_station:main',
            'smartphone = my_py_pkg.smartphone:main',
            'turtle_square = my_py_pkg.turtle_square:main',
            'set_side_length = my_py_pkg.set_side_length:main',
            'turtle_summoner = my_py_pkg.turtle_summoner:main',
            'battery = my_py_pkg.battery:main',
            'led_panel = my_py_pkg.led_panel:main',
            'turtle_controller = my_py_pkg.turtle_controller:main',
            'agv_commander = my_py_pkg.agv_commander:main',
            'charging_station = my_py_pkg.charging_station:main',
        ],
    },
)
