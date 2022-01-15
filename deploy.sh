#!/bin/sh

public_repo="fifionachow.github.io"
backend_repo_path="/Users/fionachow/Git/fifionachow"

# If a command fails then the deploy stops
set -e

printf "\033[0;32mDeploying updates to GitHub...\033[0m\n"

cd $backend_repo_path

# Build the project
hugo -d ../$public_repo

# Go To Public folder
cd ../$public_repo

# Add changes to git.
git add .

# Commit changes.
msg="rebuilding site $(date)"
if [ -n "$*" ]; then
	msg="$*"
fi

git commit -m "$msg"

# Push source and build repos.
git push origin dev

printf "\033[0;32mPush to $public_repo...\033[0m\n"