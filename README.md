# Thermodog - Lab Monitor

Temperature logging and alerting using AWS SNS.

## Acknowledgements

Using the following code for multiple-channel setups.

https://github.com/Tuckie/max31855
## Install
- need to install python-dev deb, i.e., `sudo apt-get install python-dev`
- need to get updated versions of the following python packages: `wheel`, `setuptools`, `virtualenv` and `pip` itself. Or at least I have had to do this on new Raspbian installs. `sudo pip install -U wheek setuptools pip-tools`


## TODO

o Use automatic deploy functionality to keep the boxes up to date

o Change password for pi user for monitors(chione,boreas,thucydides)

o Change name of thucidydes to better greek god.

o Better feed to web page

o Better configuration through web page

o Stop/acknowledge alert using text.

o Heartbeat - service to notify you if service goes down. A timed
lambda would be the best, or maybe clowdwatch.

### Done

o Allow configuration-file based setup

o Setup AWS role for ThermoDog boxes

o Setup Email group for receiving ThermoDog notifications: `lab-monitor`

o Flag for disabling interaction with AWS, purely local logging

o Columnar logging output, input argument for log filename, separate
program log from data log

o Add Thermodog name to data-log output by passing monitor pointer to
receive.
