#!/usr/bin/env bash
set -o errexit  # Exit on error

# Build React frontend
cd hospital-recommender-client
npm install
npm run build

# Copy React build into FastAPI's static folder
rm -rf ../hospital-recommender-server/static
mkdir -p ../hospital-recommender-server/static
cp -r dist/* ../hospital-recommender-server/static/

# Go back to backend
cd ../hospital-recommender-server
