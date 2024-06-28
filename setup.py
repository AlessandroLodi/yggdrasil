from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="your-project-name",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A short description of your project",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AlessandroLodi/your-repo-name",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        # List your project dependencies here
        # "requests>=2.25.1",
        # "numpy>=1.20.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.2.3",
            "flake8>=3.9.0",
        ],
    },
    entry_points={
        "console_scripts": [
            # Add any command-line scripts here
            # "your-script-name=your_package.module:function",
        ],
    },
)
