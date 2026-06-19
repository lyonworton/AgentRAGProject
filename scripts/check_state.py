"""Reset stuck documents and re-trigger ingestion."""
import subprocess

# Reset all pending/processing documents to error so they can be re-ingested
result = subprocess.run(
    ["docker", "exec", "agentragproject-postgres-1", "psql", "-U", "agentrag", "-d", "agentrag", "-t", "-A", "-c",
     "UPDATE documents SET status = 'error', error_message = 'Reset for re-ingestion' WHERE status IN ('pending', 'processing'); SELECT count(*) FROM documents WHERE status = 'error' AND error_message = 'Reset for re-ingestion';"],
    capture_output=True, text=True
)
print("Result:", result.stdout.strip(), result.stderr.strip())
