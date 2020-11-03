#!/bin/bash
TZ=CST-8 date +%Y%m%dt%H%M%S > updated.txt
git rev-parse --verify HEAD > version.txt
