#!/usr/bin/env python
"""
GitHub Webhook Development Server
================================

This script starts a FastAPI development server and sets up smee.io 
for GitHub webhook testing. Smee.io is a specialized service for 
GitHub webhook development.

Usage:
    python tools/start_webhook_dev.py
"""

import os
import sys
import time
import signal
import subprocess
import requests
import logging
import webbrowser
import platform
import json
from pathlib import Path
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("webhook-dev")

# Configuration
API_PORT = 8000
WEBHOOK_PATH = "/api/github/webhook"  # Matches the path in github_webhook.py
SMEE_CLIENT_INSTALLED = False

def is_npm_installed():
    """Check if npm is installed"""
    try:
        shell = platform.system().lower() == "windows"
        subprocess.run(
            ["npm", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            shell=shell
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def install_smee_client():
    """Install smee-client if not already installed"""
    global SMEE_CLIENT_INSTALLED
    
    try:
        shell = platform.system().lower() == "windows"
        # Check if smee is installed globally
        result = subprocess.run(
            ["npx", "smee", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell
        )
        if result.returncode == 0:
            logger.info("smee-client is already installed")
            SMEE_CLIENT_INSTALLED = True
            return True
    except:
        pass
    
    # Install smee-client globally
    logger.info("Installing smee-client...")
    try:
        shell = platform.system().lower() == "windows"
        result = subprocess.run(
            ["npm", "install", "-g", "smee-client"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell
        )
        if result.returncode != 0:
            logger.error(f"Failed to install smee-client: {result.stderr.decode()}")
            return False
        
        SMEE_CLIENT_INSTALLED = True
        logger.info("smee-client installed successfully")
        return True
    except Exception as e:
        logger.error(f"Error installing smee-client: {str(e)}")
        return False

def create_smee_channel():
    """Create a new smee.io channel"""
    try:
        # Direct approach: generate a UUID and use it as the channel name
        channel_id = str(uuid.uuid4())
        webhook_url = f"https://smee.io/{channel_id}"
        
        logger.info(f"Created new smee.io channel: {webhook_url}")
        return webhook_url
    except Exception as e:
        logger.error(f"Error creating smee.io channel: {str(e)}")
        return None

def save_webhook_url(webhook_url):
    """Save the webhook URL to a configuration file"""
    config_path = Path("tools") / "webhook_config.json"
    try:
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
        else:
            config = {}
        
        config["webhook_url"] = webhook_url
        config["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            
        return True
    except Exception as e:
        logger.error(f"Error saving webhook URL: {str(e)}")
        return False

def load_webhook_url():
    """Load a previously saved webhook URL"""
    config_path = Path("tools") / "webhook_config.json"
    try:
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
            return config.get("webhook_url")
        return None
    except Exception as e:
        logger.error(f"Error loading webhook URL: {str(e)}")
        return None

def handle_exit(api_process, smee_process):
    """Clean up processes on exit"""
    logger.info("Shutting down...")
    
    if smee_process:
        logger.info("Terminating smee client")
        try:
            # On Windows, we need to use taskkill to properly terminate processes
            if platform.system().lower() == "windows":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(smee_process.pid)], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
            else:
                smee_process.terminate()
                smee_process.wait(timeout=5)
        except Exception as e:
            logger.warning(f"Error terminating smee client: {str(e)}")
            try:
                smee_process.kill()
            except:
                pass
    
    if api_process:
        logger.info("Terminating API server")
        try:
            api_process.terminate()
            api_process.wait(timeout=5)
        except Exception as e:
            logger.warning(f"Error terminating API server: {str(e)}")
            try:
                api_process.kill()
            except:
                pass
    
    logger.info("Shutdown complete")

def start_smee_client(webhook_url):
    """Start the smee client to forward webhooks"""
    shell = platform.system().lower() == "windows"
    target_url = f"http://localhost:{API_PORT}{WEBHOOK_PATH}"
    
    logger.info(f"Starting smee client to forward webhooks from {webhook_url} to {target_url}")
    
    cmd = ["npx", "smee", "-u", webhook_url, "-t", target_url]
    
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
        shell=shell
    )

def main():
    """Start development environment with smee.io webhook proxy"""
    # Check if npm is installed
    if not is_npm_installed():
        logger.error("""
npm is not installed. You need npm to use the smee.io client.
Please install Node.js from https://nodejs.org/
""")
        sys.exit(1)
    
    # Install smee client if needed
    if not install_smee_client():
        logger.error("Failed to install smee-client. Cannot continue.")
        sys.exit(1)
    
    # Get or create webhook URL
    webhook_url = load_webhook_url()
    if not webhook_url:
        logger.info("No saved webhook URL found. Creating a new smee.io channel...")
        webhook_url = create_smee_channel()
        if not webhook_url:
            logger.error("Failed to create smee.io channel. Cannot continue.")
            sys.exit(1)
        save_webhook_url(webhook_url)
    
    # Start processes
    api_process = None
    smee_process = None
    
    try:
        # Start the API server using the app.py entry point
        logger.info(f"Starting FastAPI server on port {API_PORT}")
        shell = platform.system().lower() == "windows"
        api_process = subprocess.Popen(
            ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", str(API_PORT), "--reload"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            shell=shell
        )
        
        # Give the API server time to start
        time.sleep(2)
        
        # Start smee client
        smee_process = start_smee_client(webhook_url)
        
        # Open browser with setup instructions
        try:
            webbrowser.open(webhook_url)
        except:
            pass
        
        # Display webhook URL and setup information
        logger.info(f"""
Development environment is running!
=================================
API Server: http://localhost:{API_PORT}
Webhook Proxy URL: {webhook_url}

GitHub App Setup:
1. Use this Webhook URL in your GitHub App settings: {webhook_url}
2. Generate a webhook secret and add it to your .env file as GITHUB_WEBHOOK_SECRET
3. Set up the required permissions and events in your GitHub App

Press Ctrl+C to stop the development environment
""")
        
        # Set up signal handlers
        def signal_handler(sig, frame):
            handle_exit(api_process, smee_process)
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Stream logs from both processes
        logger.info("Streaming server logs:")
        while True:
            # Read from API process
            if api_process and api_process.stdout:
                while True:
                    output = api_process.stdout.readline()
                    if not output:
                        break
                    print(f"API: {output.strip()}")
            
            # Read from smee process
            if smee_process and smee_process.stdout:
                while True:
                    output = smee_process.stdout.readline()
                    if not output:
                        break
                    print(f"SMEE: {output.strip()}")
            
            # Check if processes are still running
            if api_process and api_process.poll() is not None:
                logger.error("API server process terminated unexpectedly")
                break
            
            if smee_process and smee_process.poll() is not None:
                logger.error("Smee client process terminated unexpectedly")
                break
            
            # Small delay to prevent CPU hogging
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        pass
    finally:
        handle_exit(api_process, smee_process)

if __name__ == "__main__":
    main() 