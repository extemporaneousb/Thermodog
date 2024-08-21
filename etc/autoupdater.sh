#!/bin/bash

export PATH=/usr/local/bin:${PATH}

THERMODOG_HOME=${THERMODOG_HOME:-/home/pi/thermodog}

pushd $THERMODOG_HOME

git checkout master
CUR_HASH=`git rev-parse --short HEAD`
git pull
NEW_HASH=`git rev-parse --short HEAD`

if [[ $NEW_HASH != $CUR_HASH ]];
then
    sudo service thermodog stop
    make clean && make install && make install-service
    if [[ $? != 0 ]];
    then
       echo Build failed, restarting previous version!
       git checkout $CUR_HASH
       make clean && make install && make install-service
    else
        echo Build successful!
    fi
    echo Starting Thermodog service ...
    sudo systemctl daemon-reload
    sudo service thermodog start

else
    echo Doing nothing because "$CUR_HASH == $NEW_HASH"
fi

popd
