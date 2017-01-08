#!/bin/sh
sed -e s/BRANCHNAME/${TRAVIS_BRANCH}/ -e s/GITREV/$(git rev-parse --short HEAD)/ bintray-template.json > bintray.json
