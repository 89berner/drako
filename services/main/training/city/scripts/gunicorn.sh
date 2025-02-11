#!/bin/bash
gunicorn --chdir /app manager:app --access-logfile - --error-logfile - --log-level debug -w 2 --threads 2 -b 0.0.0.0:4000