#!/bin/sh
sed -e s/BRANCHNAME/$(git symbolic-ref --short HEAD)/ -e s/GITREV/$(git rev-parse --short HEAD)/ bintray-template.json > bintray.json
