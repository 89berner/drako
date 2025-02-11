#!/bin/bash

# Fetch the IP from the specified URL
IP=$(curl -LSs 'https://ratedby.app/givemetheippleasenow' | tr -d '\n')

# Check if the IP is either empty or equals to 178.84.132.195
if [ -z "$IP" ] || [ "$IP" = '178.84.132.195' ]; then
    echo "The fetched IP is either empty or equals to 178.84.132.195, exiting with error."
    exit 1
fi

echo "The fetched IP is: $IP"
exit 0