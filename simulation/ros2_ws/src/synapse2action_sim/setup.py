from glob import glob
from setuptools import find_packages, setup


package_name = "synapse2action_sim"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "LICENSE"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
        (f"share/{package_name}/config", glob("config/*.yaml")),
        (f"share/{package_name}/worlds", glob("worlds/*.sdf")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Synapse2Action maintainers",
    maintainer_email="maintainers@synapse2action.invalid",
    description="Gazebo Harmonic navigation simulation for Synapse2Action.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "obstacle_publisher = synapse2action_sim.obstacle_publisher:main",
        ],
    },
)
