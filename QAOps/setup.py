from setuptools import setup, find_packages

setup(
    name="fault-localizer",
    version="0.1.0",
    description="IntelligentOps Fault Localizer Agent for commit fault localization.",
    author="Murtuza",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "python-dotenv",
        "langchain",
        "langchain_core",
        "langchain_google_genai",
        "langchain_openai",
        "langgraph",
        "pydantic",
        "PyGithub"
    ],
    entry_points={
        "console_scripts": [
            "fault-localizer=fault_localizer.cli:main",
        ],
    },
)
