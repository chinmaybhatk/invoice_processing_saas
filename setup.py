from setuptools import setup, find_packages

with open("requirements.txt") as f:
	requirements = f.read().strip().split("\n")

setup(
	name="invoice_processing_saas",
	version="1.0.0",
	author="Your Company",
	author_email="admin@yourcompany.com",
	description="SaaS Invoice Processing Automation with AI-powered extraction",
	long_description="""
	A comprehensive SaaS solution for automated invoice processing using AI-powered
	data extraction (OpenAI/Azure) with seamless integration to accounting systems.
	Built on Frappe framework with n8n workflow automation.
	""",
	long_description_content_type="text/markdown",
	url="https://github.com/chinmaybhatk/invoice_processing_saas",
	packages=find_packages(),
	classifiers=[
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: MIT License",
		"Operating System :: OS Independent",
	],
	python_requires=">=3.6",
	install_requires=requirements,
	include_package_data=True,
	zip_safe=False
)