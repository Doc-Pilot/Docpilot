import logging
from typing import Dict, Any, List
import os

from src.agents import (
    BaseAgent,
    GeneratorAgent,
    AgentConfig,
    GenerationContext, 
    GeneratedDocumentation, 
    DocType
)
from src.utils.repo_scanner import RepoScanner
from src.agents.change_detector_agent import ChangeDetectorAgent, ChangeDetectionInput
from src.agents.drift_monitor_agent import DriftMonitorAgent, DriftDetectionInput
from src.agents.gitops_agent import GitOpsAgent, PRCreationInput

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
        
        results = {}
        
        # Clone the repository locally if needed
        # (In a real implementation, this would clone the repo)
        repo_path = f"/tmp/{repo_name.replace('/', '_')}"
        
        # Use ChangeDetectorAgent to detect code changes
        change_detector = ChangeDetectorAgent()
        changes = await change_detector.detect_changes(
            ChangeDetectionInput(
                repo_path=repo_path,
                base_ref="HEAD~1",
                target_ref="HEAD",
                file_patterns=["*.py"]
            )
        )
        results["detected_changes"] = changes.changes
        
        # Use DriftMonitorAgent to check for documentation drift
        drift_monitor = DriftMonitorAgent()
        drift_results = await drift_monitor.check_drift(
            DriftDetectionInput(
                repo_path=repo_path,
                files=modified_files
            )
        )
        results["documentation_drift"] = drift_results.issues
        
        # Generate documentation for modified files
        generator = GeneratorAgent()
        context = GenerationContext(
            repo_path=repo_path,
            changed_files=modified_files,
            detected_changes=changes.changes
        )
        
        doc_results = await generator.generate(context)
        results["documentation_updated"] = doc_results
        
        return {
            "status": "success",
            "repository": repo_name,
            "branch": ref,
            "processed_files": len(modified_files),
            "results": results
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
        base_sha = pr.get("base", {}).get("sha")
        
        logger.info(f"Processing PR #{pr_number} in {repo_name}")
        
        # Clone the repository locally if needed
        # (In a real implementation, this would clone the repo)
        repo_path = f"/tmp/{repo_name.replace('/', '_')}"
        
        results = {}
        
        # Use ChangeDetectorAgent to detect code changes in the PR
        change_detector = ChangeDetectorAgent()
        changes = await change_detector.detect_changes(
            ChangeDetectionInput(
                repo_path=repo_path,
                base_ref=base_sha,
                target_ref=head_sha,
                file_patterns=["*.py"]
            )
        )
        results["detected_changes"] = changes.changes
        
        # Use DriftMonitorAgent to check for documentation drift
        drift_monitor = DriftMonitorAgent()
        drift_results = await drift_monitor.check_drift(
            DriftDetectionInput(
                repo_path=repo_path,
                files=changes.changes.get("changed_files", [])
            )
        )
        results["documentation_drift"] = drift_results.issues
        
        # Generate documentation suggestions for the PR
        generator = GeneratorAgent()
        context = GenerationContext(
            repo_path=repo_path,
            changed_files=changes.changes.get("changed_files", []),
            detected_changes=changes.changes
        )
        
        doc_results = await generator.generate(context)
        results["documentation_suggestions"] = doc_results
        
        return {
            "status": "success",
            "repository": repo_name,
            "pr_number": pr_number,
            "results": results
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
        
        # Clone the repository locally if needed
        # (In a real implementation, this would clone the repo)
        repo_path = f"/tmp/{repo_name.replace('/', '_')}"
        
        results = {}
        
        # Check if issue is specifically about certain documentation topics
        issue_title = issue.get("title", "").lower()
        issue_body = issue.get("body", "").lower()
        
        # For documentation-related issues, use DriftMonitorAgent to check for problems
        drift_monitor = DriftMonitorAgent()
        
        # Determine which files to check based on the issue content
        files_to_check = []
        
        if "readme" in issue_title or "readme" in issue_body:
            files_to_check.append("README.md")
        
        if "api" in issue_title or "api doc" in issue_body:
            # In a real implementation, you would identify API files here
            # For now just use a placeholder pattern
            files_to_check.extend(["*api*.py", "*routes*.py", "*views*.py"])
        
        # If no specific files mentioned, check all Python files
        if not files_to_check:
            files_to_check = ["*.py"]
        
        # Check for documentation drift
        drift_results = await drift_monitor.check_drift(
            DriftDetectionInput(
                repo_path=repo_path,
                files=files_to_check
            )
        )
        results["documentation_issues"] = drift_results.issues
        
        # Generate suggestions
        generator = GeneratorAgent()
        context = GenerationContext(
            repo_path=repo_path,
            issue_title=issue_title,
            issue_body=issue_body,
            documentation_issues=drift_results.issues
        )
        
        suggestions = await generator.generate(context)
        results["documentation_suggestions"] = suggestions
        
        return {
            "status": "success",
            "repository": repo_name,
            "issue_number": issue_number,
            "results": results
        }
    
    except Exception as e:
        logger.exception(f"Error processing issue event: {str(e)}")
        return {"status": "error", "message": str(e)} 