#!/bin/sh
TIMEOUT=300 # high in case we start with an already running training at it takes long to start the worker
# todo make it faster
gunicorn --chdir /app training_prediction:application --access-logfile - --error-logfile - --timeout $TIMEOUT -w 1 --threads 1 -b 0.0.0.0:4000