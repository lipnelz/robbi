#!/bin/bash
cd /app && git pull origin main
exec python src/main.py