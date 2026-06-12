from typing import List, Dict, Any
from github import Github, Commit
from github.GithubException import GithubException
from fault_localizer.core.config import settings

class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, repo_name: str, token: str = None):
        """
        Initialize the GitHub client.
        
        Args:
            repo_name (str): The repository name in 'owner/repo' format.
            token (str): GitHub Personal Access Token. If not provided,
                         it attempts to read from config.
        """
        self.token = token or settings.GITHUB_TOKEN
        if not self.token:
            raise ValueError("GITHUB_TOKEN is missing. Please provide it as an environment variable.")
        
        self.gh = Github(self.token)
        self.repo = self.gh.get_repo(repo_name)

    def get_commits_in_range(self, base_commit: str, head_commit: str) -> List[Dict[str, Any]]:
        """
        Fetch all commits between base_commit (last passing) and head_commit (first failing).
        Returns a list of dictionaries with commit details, including diffs.
        """
        try:
            comparison = self.repo.compare(base_commit, head_commit)
            commits_data = []
            
            for commit in comparison.commits:
                # Get detailed commit info including files changed (diffs)
                detailed_commit = self.repo.get_commit(commit.sha)
                
                files_changed = []
                for file in detailed_commit.files:
                    files_changed.append({
                        "filename": file.filename,
                        "status": file.status,
                        "additions": file.additions,
                        "deletions": file.deletions,
                        "patch": file.patch if file.patch else "No patch available (binary or too large)"
                    })

                commits_data.append({
                    "sha": commit.sha,
                    "author": commit.commit.author.name if commit.commit.author else "Unknown",
                    "date": commit.commit.author.date.isoformat() if commit.commit.author else "Unknown",
                    "message": commit.commit.message,
                    "files": files_changed
                })
            return commits_data
        except GithubException as e:
            print(f"Error fetching commits: {e}")
            return []

    def create_revert_pr(self, commit_sha: str, base_branch: str = None) -> str:
        """
        Creates a revert branch and a PR to revert a specific commit autonomously.
        Returns the PR URL if successful.
        """
        import subprocess
        import tempfile
        import os

        # Use the default branch of the repo
        base_branch = self.repo.default_branch
        revert_branch_name = f"revert-{commit_sha[:7]}"
        
        # Build clone URL with token
        clone_url = f"https://x-access-token:{self.token}@github.com/{self.repo.full_name}.git"

        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"      [Git] Cloning repository into temporary directory...")
            
            try:
                # 1. Clone
                subprocess.run(
                    ["git", "clone", "--branch", base_branch, clone_url, tmpdir],
                    check=True, capture_output=True, text=True
                )

                # 2. Configure Git User (if not set globally)
                subprocess.run(["git", "config", "user.email", "agent@intelligentops.ai"], cwd=tmpdir, check=True, capture_output=True, text=True)
                subprocess.run(["git", "config", "user.name", "QAOps Agent"], cwd=tmpdir, check=True, capture_output=True, text=True)

                # 3. Checkout new branch
                print(f"      [Git] Creating branch '{revert_branch_name}'...")
                subprocess.run(["git", "checkout", "-b", revert_branch_name], cwd=tmpdir, check=True, capture_output=True, text=True)
                
                # 4. Revert commit
                print(f"      [Git] Reverting commit {commit_sha[:7]}...")
                subprocess.run(["git", "revert", "--no-edit", commit_sha], cwd=tmpdir, check=True, capture_output=True, text=True)
                
                # 5. Push (force push in case branch already exists from previous run)
                print(f"      [Git] Pushing branch to origin...")
                subprocess.run(["git", "push", "-f", "origin", revert_branch_name], cwd=tmpdir, check=True, capture_output=True, text=True)
                
            except subprocess.CalledProcessError as e:
                print(f"      [Error] Git operation failed. Command: {e.cmd}")
                print(f"      [Error] Git Stderr: {e.stderr}")
                
                # If the revert failed due to conflicts, create a GitHub Issue to notify the team
                if "git', 'revert" in str(e.cmd):
                    print("      [Info] Revert failed (likely due to merge conflicts). Creating an Issue instead...")
                    subprocess.run(["git", "revert", "--abort"], cwd=tmpdir, capture_output=True)
                    try:
                        issue = self.repo.create_issue(
                            title=f"⚠️ Manual Revert Required: {commit_sha[:7]}",
                            body=f"The QAOps Agent identified commit `{commit_sha}` as the root cause of the recent CI/CD failure.\n\nHowever, the agent could not automatically revert it due to a **Merge Conflict**.\n\nPlease manually resolve the conflicts and revert the commit.\n\n<details><summary>Git Error Output</summary>\n\n```text\n{e.stderr}\n```\n</details>"
                        )
                        print(f"      [GitHub] Created issue for manual intervention: {issue.html_url}")
                    except Exception as issue_e:
                        print(f"      [Error] Failed to create GitHub Issue: {issue_e}")
                        
                return None

        # 6. Create PR via GitHub API
        print(f"      [GitHub] Opening Pull Request...")
        try:
            pr = self.repo.create_pull(
                title=f"Revert: {commit_sha[:7]}",
                body=f"Automated Revert by QAOps Agent.\n\nThis PR reverts commit `{commit_sha}` as it was identified to cause test failures.",
                head=revert_branch_name,
                base=base_branch
            )
            return pr.html_url
        except Exception as e:
            print(f"      [Error] Failed to create Pull Request via API: {e}")
            return None
