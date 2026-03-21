#!/usr/bin/env python3
"""
Test Runner AI Execution
Quick test per verificare l'integrazione AI del runner
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Add runner to path
sys.path.insert(0, str(Path(__file__).parent))

from runner.auth import AuthManager
from runner.cloud_client import AIBackendClient
from loguru import logger

def test_runner_execute():
    """Test dell'endpoint runner/execute"""
    
    # Setup auth
    auth = AuthManager()
    
    if not auth.is_authenticated():
        logger.error("Runner non autenticato. Esegui 'akaion login' prima.")
        return
    
    # Create AI client
    ai_client = AIBackendClient(
        api_key=auth.get_firebase_token(),
        runner_id=auth.get_runner_id(),
        base_url=os.getenv("AKAION_AI_URL")
    )
    
    # Test command
    command = "Analizza i file Python in questa directory e dimmi quanti sono"
    
    logger.info(f"Executing command: {command}")
    
    result = ai_client.runner_execute(
        command=command,
        working_directory=os.getcwd(),
        available_tools=["filesystem", "shell"],
        permissions={"filesystem": {"allowed_paths": ["~/Documents"]}},
        temperature=0.7
    )
    
    if result:
        logger.success("✅ AI Response received!")
        logger.info(f"Success: {result.get('success')}")
        logger.info(f"Response: {result.get('response')}")
        logger.info(f"Error: {result.get('error')}")
        logger.info(f"Actions: {result.get('actions')}")
        logger.info(f"Model: {result.get('model_used')}")
        logger.info(f"Tokens: {result.get('tokens_used')}")
        
        # Show full result for debugging
        logger.debug(f"Full result: {result}")
    else:
        logger.error("❌ No response from AI")

if __name__ == "__main__":
    test_runner_execute()
