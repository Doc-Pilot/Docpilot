"""
GitHub Installation Store
========================

Store and manage GitHub App installations.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import aiofiles
import asyncio

from ..utils.config import get_settings
from ..utils.logging import logger

class InstallationStore:
    """
    Store and manage GitHub App installations.
    
    This class handles:
    - Storing installation metadata
    - Refreshing tokens
    - Tracking repository access
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the installation store.
        
        Args:
            storage_path: Path to store installation data (defaults to data/installations.json)
        """
        self.settings = get_settings()
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "installations.json"
        )
        self.installations: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        
    async def load(self) -> None:
        """Load installations from storage file."""
        try:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # If file doesn't exist, create an empty one
            if not os.path.exists(self.storage_path):
                async with aiofiles.open(self.storage_path, "w") as f:
                    await f.write("{}")
                return
                
            # Load existing installations
            async with aiofiles.open(self.storage_path, "r") as f:
                content = await f.read()
                self.installations = json.loads(content)
                
            logger.info(f"Loaded {len(self.installations)} GitHub App installations")
        except Exception as e:
            logger.exception(f"Error loading installations: {str(e)}")
            # Initialize with empty dict if there's an error
            self.installations = {}
            
    async def save(self) -> None:
        """Save installations to storage file."""
        try:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            async with aiofiles.open(self.storage_path, "w") as f:
                await f.write(json.dumps(self.installations, indent=2))
                
            logger.info(f"Saved {len(self.installations)} GitHub App installations")
        except Exception as e:
            logger.exception(f"Error saving installations: {str(e)}")
            
    async def add_installation(
        self,
        installation_id: str,
        account_name: str,
        account_type: str,
        repositories: List[str],
        access_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Add or update an installation.
        
        Args:
            installation_id: GitHub App installation ID
            account_name: Account username or organization name
            account_type: 'User' or 'Organization'
            repositories: List of repository names accessible to this installation
            access_token: Installation access token (optional)
            token_expires_at: Token expiration datetime (optional)
            
        Returns:
            Installation data
        """
        async with self.lock:
            # Ensure installations are loaded
            if not self.installations:
                await self.load()
                
            # Create or update installation data
            installation_data = {
                "installation_id": installation_id,
                "account_name": account_name,
                "account_type": account_type,
                "repositories": repositories,
                "created_at": self.installations.get(installation_id, {}).get(
                    "created_at", datetime.now().isoformat()
                ),
                "updated_at": datetime.now().isoformat(),
            }
            
            # Add token data if provided
            if access_token and token_expires_at:
                installation_data["access_token"] = access_token
                installation_data["token_expires_at"] = token_expires_at.isoformat()
                
            # Store the installation
            self.installations[installation_id] = installation_data
            
            # Save to disk
            await self.save()
            
            return installation_data
            
    async def remove_installation(self, installation_id: str) -> bool:
        """
        Remove an installation.
        
        Args:
            installation_id: GitHub App installation ID
            
        Returns:
            True if removed, False if not found
        """
        async with self.lock:
            # Ensure installations are loaded
            if not self.installations:
                await self.load()
                
            # Remove the installation if it exists
            if installation_id in self.installations:
                del self.installations[installation_id]
                
                # Save to disk
                await self.save()
                
                return True
                
            return False
            
    async def get_installation(self, installation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get installation data.
        
        Args:
            installation_id: GitHub App installation ID
            
        Returns:
            Installation data or None if not found
        """
        # Ensure installations are loaded
        if not self.installations:
            await self.load()
            
        return self.installations.get(installation_id)
        
    async def find_installation_for_repo(
        self,
        owner: str,
        repo: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find the installation that has access to a specific repository.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            
        Returns:
            Installation data or None if not found
        """
        # Ensure installations are loaded
        if not self.installations:
            await self.load()
            
        full_name = f"{owner}/{repo}"
        
        # Search installations for this repository
        for installation_id, installation in self.installations.items():
            # Check if this installation has the account name
            if installation["account_name"].lower() == owner.lower():
                # Check if repos list includes this repo
                if full_name in installation.get("repositories", []):
                    return installation
                    
        return None
        
    async def update_token(
        self,
        installation_id: str,
        access_token: str,
        expires_at: datetime
    ) -> None:
        """
        Update the access token for an installation.
        
        Args:
            installation_id: GitHub App installation ID
            access_token: New access token
            expires_at: Token expiration datetime
        """
        async with self.lock:
            # Ensure installations are loaded
            if not self.installations:
                await self.load()
                
            # Update if installation exists
            if installation_id in self.installations:
                installation = self.installations[installation_id]
                installation["access_token"] = access_token
                installation["token_expires_at"] = expires_at.isoformat()
                installation["updated_at"] = datetime.now().isoformat()
                
                # Save to disk
                await self.save()
                
    async def get_valid_token(
        self,
        installation_id: str
    ) -> Optional[str]:
        """
        Get a valid access token for an installation.
        
        Returns None if no token is available or if the token has expired.
        When this returns None, a new token should be generated.
        
        Args:
            installation_id: GitHub App installation ID
            
        Returns:
            Valid access token or None
        """
        # Ensure installations are loaded
        if not self.installations:
            await self.load()
            
        installation = self.installations.get(installation_id)
        if not installation:
            return None
            
        # Check if token exists and is still valid
        token = installation.get("access_token")
        expires_str = installation.get("token_expires_at")
        
        if not token or not expires_str:
            return None
            
        try:
            # Parse expiration time
            expires_at = datetime.fromisoformat(expires_str)
            
            # Add a buffer to ensure we don't use tokens that are about to expire
            buffer = timedelta(minutes=5)
            
            # Check if token is still valid
            if datetime.now() + buffer < expires_at:
                return token
        except Exception as e:
            logger.warning(f"Error parsing token expiration: {str(e)}")
            
        return None 