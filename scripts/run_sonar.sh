#!/bin/bash

# Configuration
SONAR_HOST_URL="http://192.168.1.86:9000"
SONAR_LOGIN="admin"
SONAR_PASSWORD="patilla1"
PROJECT_KEY="research-agent"
COVERAGE_REPORT="coverage.xml"

# Ensure coverage report exists
if [ ! -f "$COVERAGE_REPORT" ]; then
    echo "Warning: $COVERAGE_REPORT not found. SonarQube analysis may lack coverage data."
    echo "Please run tests first to generate coverage."
fi

echo "Running SonarQube Scanner..."
docker run --rm \
    -v "$(pwd):/usr/src" \
    sonarsource/sonar-scanner-cli \
    -Dsonar.projectKey=$PROJECT_KEY \
    -Dsonar.sources=src \
    -Dsonar.tests=tests \
    -Dsonar.python.version=3.12 \
    -Dsonar.python.coverage.reportPaths=$COVERAGE_REPORT \
    -Dsonar.host.url=$SONAR_HOST_URL \
    -Dsonar.login=$SONAR_LOGIN \
    -Dsonar.password=$SONAR_PASSWORD \
    -Dsonar.scm.disabled=true

echo "SonarQube analysis complete."
