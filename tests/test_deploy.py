"""Tests for the deploy functionality."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from webhookclient.main import deploy

TEST_REPO = "appenz/github-webhook-watcher"

def test_deploy_no_github_repo():
    """Test deploy fails when GITHUB_REPO is not set."""
    with pytest.raises(RuntimeError, match="GITHUB_REPO environment variable must be set"):
        deploy()

@patch("pathlib.Path.exists")
@patch("pathlib.Path.mkdir")
@patch("subprocess.run")
def test_deploy_clone_new_repo(mock_run, mock_mkdir, mock_exists):
    """Test cloning a new repository."""
    # Setup mocks
    mock_exists.return_value = False
    mock_run.return_value.stdout = "Cloning into 'github-webhook-watcher'..."
    
    # Set environment variables
    os.environ["GITHUB_REPO"] = TEST_REPO
    os.environ["LOCAL_DIRECTORY"] = "/tmp/test"
    
    # Run deploy
    deploy()
    
    # Verify mkdir was called
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    # Verify git clone was called
    mock_run.assert_called_once_with(
        ["git", "clone", f"https://github.com/{TEST_REPO}.git"],
        cwd="/tmp/test",
        capture_output=True,
        text=True,
        check=True
    )

@patch("pathlib.Path.exists")
@patch("pathlib.Path.mkdir")
@patch("subprocess.run")
def test_deploy_pull_existing_repo(mock_run, mock_mkdir, mock_exists):
    """Test pulling an existing repository."""
    # Setup mocks
    mock_exists.return_value = True
    mock_run.return_value.stdout = "Already up to date."
    
    # Set environment variables
    os.environ["GITHUB_REPO"] = TEST_REPO
    os.environ["LOCAL_DIRECTORY"] = "/tmp/test"
    
    # Run deploy
    deploy()
    
    # Verify mkdir was called
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    # Verify git pull was called
    mock_run.assert_called_once_with(
        ["git", "pull", "origin"],
        cwd="/tmp/test/github-webhook-watcher",
        capture_output=True,
        text=True,
        check=True
    )

@patch("pathlib.Path.exists")
@patch("pathlib.Path.mkdir")
@patch("subprocess.run")
def test_deploy_git_error(mock_run, mock_mkdir, mock_exists):
    """Test handling of git command errors."""
    # Setup mocks
    mock_exists.return_value = True
    mock_run.side_effect = Exception("Git error")
    
    # Set environment variables
    os.environ["GITHUB_REPO"] = TEST_REPO
    
    # Run deploy and verify error handling
    with pytest.raises(RuntimeError, match="Unexpected error during deploy: Git error"):
        deploy()