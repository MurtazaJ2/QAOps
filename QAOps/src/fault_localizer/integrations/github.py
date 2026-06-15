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

    def create_revert_pr(self, commit_shas: List[str], base_branch: str = None) -> str:
        """
        Creates a new branch, reverts the specified commits, pushes, and opens a PR.
        commit_shas should be ordered from newest to oldest for clean reverts.
        Returns the PR URL or None if failed.
        """
        if not commit_shas:
            return None
            
        base_branch = base_branch or self.repo.default_branch
        
        # Use the first SHA for the branch name, but indicate multiple
        primary_sha = commit_shas[0][:7]
        revert_branch_name = f"revert-multiple-{primary_sha}" if len(commit_shas) > 1 else f"revert-{primary_sha}"
        
        # We need to clone the repo locally to perform the revert and push
        import tempfile
        import subprocess
        
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
                
                # 4. Revert commits sequentially
                for sha in commit_shas:
                    print(f"      [Git] Reverting commit {sha[:7]}...")
                    subprocess.run(["git", "revert", "--no-edit", sha], cwd=tmpdir, check=True, capture_output=True, text=True)
                
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
                        failed_sha = e.cmd[-1]
                        sha_list_str = ", ".join([s[:7] for s in commit_shas])
                        issue = self.repo.create_issue(
                            title=f"⚠️ Manual Revert Required: Conflict in {failed_sha[:7]}",
                            body=f"The QAOps Agent identified the following commits as root causes of the recent CI/CD failure: `{sha_list_str}`\n\nHowever, the agent could not automatically revert `{failed_sha}` due to a **Merge Conflict**.\n\nPlease manually resolve the conflicts and revert the commits.\n\n<details><summary>Git Error Output</summary>\n\n```text\n{e.stderr}\n```\n</details>"
                        )
                        print(f"      [GitHub] Created issue for manual intervention: {issue.html_url}")
                    except Exception as issue_e:
                        print(f"      [Error] Failed to create GitHub Issue: {issue_e}")
                        
                return None

        # 6. Create PR via GitHub API
        print(f"      [GitHub] Opening Pull Request...")
        try:
            sha_list_str = ", ".join([f"`{s[:7]}`" for s in commit_shas])
            pr_title = f"Revert Multiple Faulty Commits ({sha_list_str})" if len(commit_shas) > 1 else f"Revert commit {primary_sha}"
            pr_body = (
                f"🤖 **Automated Revert PR**\n\n"
                f"The QAOps Agent has detected that the following commits introduced a CI/CD failure:\n"
                f"{sha_list_str}\n\n"
                f"This PR safely reverts them to restore the pipeline to a green state."
            )
            
            pr = self.repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=revert_branch_name,
                base=base_branch
            )
            return pr.html_url
        except Exception as e:
            print(f"      [Error] Failed to create Pull Request: {e}")
            return None
