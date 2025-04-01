import logging
from typing import Dict, Any

from src.agents import DocGenerator, CodeAnalyzer, QualityChecker, DocGeneratorInput, AgentConfig

logger = logging.getLogger(__name__)

async def handle_push_event(payload: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Handle GitHub push events
    
    When code is pushed, analyze changes and update relevant documentation
    """
    try:
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        ref = payload.get("ref", "")
        commits = payload.get("commits", [])
        
        logger.info(f"Processing push to {repo_name} on {ref} with {len(commits)} commits")
        
        # Skip empty pushes or non-main branch pushes (configurable)
        if not commits or "refs/heads/main" not in ref and "refs/heads/master" not in ref:
            return {"status": "skipped", "reason": "No commits or not on main branch"}
            
        # Get the files that were modified
        modified_files = []
        for commit in commits:
            modified_files.extend(commit.get("added", []))
            modified_files.extend(commit.get("modified", []))
        
        # Remove duplicates
        modified_files = list(set(modified_files))
        
        # Generate documentation for modified files
        doc_generator = DocGenerator()
        results = await doc_generator.process_file_changes(
            repo_name=repo_name,
            branch=ref.replace("refs/heads/", ""),
            file_paths=modified_files
        )
        
        return {
            "status": "success",
            "repository": repo_name,
            "branch": ref,
            "processed_files": len(modified_files),
            "documentation_updated": results
        }
    
    except Exception as e:
        logger.exception(f"Error processing push event: {str(e)}")
        return {"status": "error", "message": str(e)}

async def handle_pull_request_event(payload: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Handle GitHub pull request events
    
    When a PR is opened or updated, analyze changes and suggest 
    documentation updates as comments
    """
    try:
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        
        # Only process opened or synchronized PRs
        if action not in ["opened", "synchronize"]:
            return {"status": "skipped", "reason": f"PR action {action} not relevant"}
            
        repo_name = repo.get("full_name")
        pr_number = pr.get("number")
        head_sha = pr.get("head", {}).get("sha")
        
        logger.info(f"Processing PR #{pr_number} in {repo_name}")
        
        # Generate documentation suggestions for the PR
        doc_generator = DocGenerator()
        suggestions = await doc_generator.process_pull_request(
            repo_name=repo_name,
            pr_number=pr_number,
            head_sha=head_sha
        )
        
        return {
            "status": "success",
            "repository": repo_name,
            "pr_number": pr_number,
            "documentation_suggestions": suggestions
        }
    
    except Exception as e:
        logger.exception(f"Error processing PR event: {str(e)}")
        return {"status": "error", "message": str(e)}

async def handle_issues_event(payload: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Handle GitHub issues events
    
    When issues related to documentation are created or modified,
    suggest documentation improvements
    """
    try:
        action = payload.get("action")
        issue = payload.get("issue", {})
        repo = payload.get("repository", {})
        
        # Only process newly opened issues or ones with the "documentation" label
        labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
        if action != "opened" and "documentation" not in labels:
            return {"status": "skipped", "reason": "Not a documentation issue"}
            
        repo_name = repo.get("full_name")
        issue_number = issue.get("number")
        
        logger.info(f"Processing documentation issue #{issue_number} in {repo_name}")
        
        # Process documentation issue
        doc_generator = DocGenerator()
        response = await doc_generator.process_documentation_issue(
            repo_name=repo_name,
            issue_number=issue_number,
            issue_title=issue.get("title", ""),
            issue_body=issue.get("body", "")
        )
        
        return {
            "status": "success",
            "repository": repo_name,
            "issue_number": issue_number,
            "response": response
        }
    
    except Exception as e:
        logger.exception(f"Error processing issue event: {str(e)}")
        return {"status": "error", "message": str(e)} 