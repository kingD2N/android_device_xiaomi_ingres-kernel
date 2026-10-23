#!/bin/bash

[ "$#" -gt 0 ] && [ "$1" = "--am" ] && FLAG=" --am"

k_ver="$(strings Image | grep 'Linux version 5.10' | cut -d ' ' -f 3)"
git add -A
git commit $FLAG -m "ingres-kernel: Update to $k_ver"
