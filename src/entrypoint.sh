#!/bin/bash
cd /app && git pull origin main
pip install --no-cache-dir -q -r requirements.txt
exec python src/main.py