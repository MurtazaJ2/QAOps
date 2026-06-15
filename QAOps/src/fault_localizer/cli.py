import argparse
from fault_localizer.core.config import settings
from fault_localizer.integrations.github import GitHubClient
from fault_localizer.utils.log_parser import LogParser
from fault_localizer.agents.fault_localizer import QAOpsAgent

def main():
    parser = argparse.ArgumentParser(description="QAOps Agent: Commit Fault Localizer")
    parser.add_argument("--repo", required=True, help="GitHub repository in format 'owner/repo'")
    parser.add_argument("--base", required=True, help="Base commit SHA (last passing)")
    parser.add_argument("--head", required=True, help="Head commit SHA (first failing)")
    parser.add_argument("--log-file", required=True, help="Path to the failure log file")
    
    parser.add_argument("--model-provider", default=settings.MODEL_PROVIDER, choices=["google", "openai", "openrouter"], help="Model provider (google, openai, or openrouter)")
    parser.add_argument("--model-name", default=settings.MODEL_NAME, help="Model name to use")
    parser.add_argument("--auto-revert", action="store_true", help="Run autonomously without interactive prompts (for CI/CD)")
    
    args = parser.parse_args()

    print("="*50)
    print("QAOps Agent: Initializing...")
    print("="*50)

    # 1. Ingest Failure Logs
    print(f"\n[1] Reading failure logs from {args.log_file}...")
    try:
        raw_log = LogParser.read_log_from_file(args.log_file)
        processed_log = LogParser.extract_failure_context(raw_log)
    except Exception as e:
        print(f"Error reading log file: {e}")
        return

    # 2. Fetch Commits from GitHub
    print(f"\n[2] Fetching commits for {args.repo} between {args.base} and {args.head}...")
    try:
        gh_client = GitHubClient(args.repo)
        commits = gh_client.get_commits_in_range(args.base, args.head)
        print(f"Found {len(commits)} commits in range.")
        if not commits:
            print("No commits found. Exiting.")
            return
    except Exception as e:
        print(f"GitHub Error: {e}")
        return

    # 3. Run Agentic Analysis
    print(f"\n[3] Starting Semantic Analysis Engine with {args.model_provider} ({args.model_name})...")
    try:
        agent = QAOpsAgent(model_provider=args.model_provider, model_name=args.model_name)
        result = agent.run(processed_log, commits)
    except Exception as e:
        print(f"Agent Error: {e}")
        return

    # 4. Report and Action
    print("\n" + "="*50)
    print("ANALYSIS REPORT")
    print("="*50)
    
    print(f"\nSummarized Failure Context:\n{result['summarized_failure']}\n")
    
    print("--- Individual Commit Scores ---")
    for commit in result.get('commits', []):
        print(f"[{commit['sha'][:7]}] Score: {commit.get('score', 0)}% | Author: {commit['author']}")
        print(f"Reasoning: {commit.get('reasoning', 'No reasoning provided')}\n")
        
    top_suspects = result.get('top_suspects', [])
    
    if top_suspects:
        print(f"🚨 FOUND {len(top_suspects)} HIGH-PROBABILITY COMMIT(S):")
        for suspect in top_suspects:
            print(f"\n- Commit: {suspect['sha'][:7]}")
            print(f"  Author: {suspect['author']}")
            print(f"  Score:  {suspect['score']}%")
            print(f"  Reason: {suspect['reasoning']}")
        
        print("\n--- ACTION ---")
        
        # Extract SHAs
        target_shas = [s['sha'] for s in top_suspects]
        sha_str = ", ".join([s[:7] for s in target_shas])
        
        if args.auto_revert:
            print(f"\n[CI Mode] Automatically initiating revert process for {sha_str}...")
            revert_pr_url = gh_client.create_revert_pr(target_shas)
            if revert_pr_url:
                print(f"\n✅ Success! A Revert PR has been automatically created here:\n  {revert_pr_url}")
            else:
                print("\n❌ Failed to create Revert PR automatically.")
        else:
            while True:
                choice = input(f"Do you want the agent to automatically revert {sha_str} and open a PR? [y/N]: ").strip().lower()
                if choice in ['y', 'yes']:
                    print("\nInitiating automated revert process...")
                    revert_pr_url = gh_client.create_revert_pr(target_shas)
                    if revert_pr_url:
                        print(f"\n✅ Success! A Revert PR has been automatically created here:\n  {revert_pr_url}")
                    else:
                        print("\n❌ Failed to create Revert PR automatically.")
                    break
                elif choice in ['n', 'no', '']:
                    print("\nSkipping automatic revert.")
                    break
                else:
                    print("Invalid input. Please enter 'y' or 'n'.")
    else:
        print("✅ No high-probability suspect commits (>= 50%) found. The failure might be environmental or flaky.")
        
    print("="*50)

if __name__ == "__main__":
    main()
