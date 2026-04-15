from setuptools import setup, find_packages

setup(
    name="workout-planner",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "click",
        "pyyaml",
        "anthropic",
        "easy-google-auth",
        "grpcio",
    ],
    entry_points={
        "console_scripts": [
            "workout-planner=workout_planner.cli:main",
        ],
    },
)
