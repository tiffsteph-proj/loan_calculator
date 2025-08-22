
#======================#
# Install, clean, test #
#======================#

install_requirements:
	@pip install -r requirements.txt


clean:
	@rm -f */version.txt
	@rm -f .coverage
	@rm -fr */__pycache__ */*.pyc __pycache__
	@rm -fr build dist
	@rm -fr BankLoan-*.dist-info
	@rm -fr BankLoan.egg-info

all: install clean