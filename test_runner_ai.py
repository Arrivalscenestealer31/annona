#!/usr/bin/env python3
"""
Test Runner AI Execution
Quick test per verificare l'integrazione AI del runner
"""
import os
import sys
import subprocess
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
    
    # Create AI client con timeout maggiore per task complessi
    ai_client = AIBackendClient(
        api_key=auth.get_firebase_token(),
        runner_id=auth.get_runner_id(),
        base_url=os.getenv("AKAION_AI_URL"),
        timeout=90  # Aumentato da 30s a 90s per task con script bash complessi
    )
    
    # Test command - Task reale di editing documento Word
    test_path = "/home/pf-5k0epy/Desktop/test"
    command = f"""Trova e lavora sui file Word (.docx) nella directory {test_path}:

1. Cerca tutti i file .docx presenti nella directory
2. Per ogni file .docx trovato:
   - Usa 'pandoc' o 'docx2txt' per estrarre il testo (se non disponibili, usa 'unzip' e 'grep' per estrarre da document.xml)
   - Leggi e analizza il contenuto
   - Identifica eventuali problemi o miglioramenti necessari
   - Crea un file di output con il contenuto migliorato/formattato
   - Genera un summary del documento in formato Markdown
3. Se non trovi file .docx, lavora sui file .txt presenti
4. Salva i risultati nella stessa directory

Esegui tutte le operazioni necessarie."""
    
    logger.info(f"🎯 Task: Work on Word documents (.docx)")
    logger.info(f"📂 Working directory: {test_path}")
    logger.info(f"📝 Command:\n{command}")
    logger.info(f"{'='*60}\n")
    
    result = ai_client.runner_execute(
        command=command,
        working_directory=test_path,
        available_tools=["filesystem", "shell"],
        permissions={"filesystem": {"allowed_paths": [test_path, "/home/pf-5k0epy/Desktop"]}},
        temperature=0.7
    )
    
    if result:
        logger.success("✅ AI Response received!")
        logger.info(f"Success: {result.get('success')}")
        logger.info(f"Response: {result.get('response')}")
        logger.info(f"Error: {result.get('error')}")
        logger.info(f"Model: {result.get('model_used')}")
        logger.info(f"Tokens: {result.get('tokens_used')}")
        
        # Execute suggested actions
        actions = result.get('actions', [])
        if actions:
            logger.info(f"\n{'='*60}")
            logger.info(f"🚀 Executing {len(actions)} suggested action(s):")
            logger.info(f"{'='*60}")
            
            for i, action in enumerate(actions, 1):
                action_type = action.get('type')
                description = action.get('description')
                payload = action.get('payload', {})
                
                logger.info(f"\n📌 Action {i}: {action_type}")
                logger.info(f"   Description: {description}")
                
                if action_type == 'shell_command':
                    cmd = payload.get('command')
                    
                    # If command is multi-line bash script, save to temp file and execute
                    if cmd and ('\n' in cmd and len(cmd) > 100):
                        logger.info(f"   📝 Multi-line script detected ({len(cmd)} chars), saving to temp file...")
                        import tempfile
                        
                        # Prepend shebang if not present
                        if not cmd.startswith("#!/bin/bash"):
                            cmd = "#!/bin/bash\n" + cmd
                        
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, dir=test_path) as f:
                            f.write(cmd)
                            script_path = f.name
                        
                        # Make script executable
                        os.chmod(script_path, 0o755)
                        logger.info(f"   📜 Script saved: {Path(script_path).name}")
                        cmd = f"bash {Path(script_path).name}"
                    
                    logger.info(f"   Command: {cmd[:100]}{'...' if len(cmd) > 100 else ''}")
                    
                    try:
                        # Execute command
                        logger.info(f"\n▶️  Executing command...")
                        result_exec = subprocess.run(
                            cmd,
                            shell=True,
                            cwd=test_path,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        
                        logger.info(f"\n{'─'*60}")
                        logger.info(f"📤 OUTPUT:")
                        logger.info(f"{'─'*60}")
                        if result_exec.stdout:
                            print(result_exec.stdout)
                        if result_exec.stderr:
                            logger.warning(f"⚠️  STDERR:\n{result_exec.stderr}")
                        logger.info(f"{'─'*60}")
                        logger.info(f"Exit code: {result_exec.returncode}")
                        
                        # Read and show any files created/modified
                        logger.info(f"\n📄 Checking for created/modified files...")
                        test_dir = Path(test_path)
                        for filepath in test_dir.glob("*"):
                            if filepath.is_file():
                                try:
                                    content = filepath.read_text()
                                    logger.info(f"\n📖 Content of {filepath.name}:")
                                    logger.info(f"{'─'*60}")
                                    print(content)
                                    logger.info(f"{'─'*60}")
                                except Exception as e:
                                    logger.debug(f"Cannot read {filepath.name}: {e}")
                        
                    except subprocess.TimeoutExpired:
                        logger.error(f"❌ Command timeout after 30s")
                    except Exception as e:
                        logger.error(f"❌ Error executing command: {e}")
            
            logger.info(f"\n{'='*60}")
        else:
            logger.warning("No actions to execute")
        
        # Show full result for debugging
        logger.debug(f"\nFull result: {result}")
    else:
        logger.error("❌ No response from AI")

if __name__ == "__main__":
    test_runner_execute()
