# INFRASTRUCTURE
import json
import os
import subprocess
from pathlib import Path

# Verified against src/logs/api_requests_opus_monitor_cc_1776092124.jsonl
_MCP_PREFIXES = {
    "iterative-dev": "mcp__plugin_iterative-dev_iterative-dev__",
    "github-research": "mcp__plugin_github-research_github__",
}

# Server definitions: (plugin_name, server_path, server_project_dir, venv_dir)
# venv_dir: which Python venv to use for extraction subprocess
_SERVERS = [
    (
        "iterative-dev",
        "/Users/brunowinter2000/Documents/ai/Meta/blank/server.py",
        "/Users/brunowinter2000/Documents/ai/Meta/blank",
        "/Users/brunowinter2000/Documents/ai/Meta/blank/venv",
    ),
    (
        "github-research",
        "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github/server.py",
        "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github",
        "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github/.venv",
    ),
]

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_OUTPUT_BASE = _PROJECT_ROOT / "src" / "logs" / "mcp_tool_schemas"

# Inline helper: executed in each server's subprocess — prints JSON array of schemas to stdout
_HELPER_CODE = '''
import asyncio, importlib.util, json, sys

server_path = sys.argv[1]
prefix = sys.argv[2]

spec = importlib.util.spec_from_file_location("_server", server_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mcp_obj = mod.mcp

tools = asyncio.run(mcp_obj.list_tools())
schemas = []
for tool in tools:
    mcp_tool = tool.to_mcp_tool()
    schemas.append({
        "name": prefix + mcp_tool.name,
        "description": mcp_tool.description,
        "input_schema": mcp_tool.inputSchema,
    })

print(json.dumps(schemas))
'''


# ORCHESTRATOR

def extract_schemas_workflow() -> None:
    """Extract MCP tool schemas from both plugin servers and write JSON files."""
    total_written = 0
    all_samples = []

    for plugin_name, server_path, server_project_dir, venv_dir in _SERVERS:
        venv_python = _ensure_venv(plugin_name, venv_dir, server_project_dir)
        schemas = _extract_plugin_schemas(plugin_name, server_path, server_project_dir, venv_python)
        written = _write_schemas(plugin_name, schemas)
        total_written += written
        print(f"[{plugin_name}] {written} schemas written to {_OUTPUT_BASE / plugin_name}/")
        if schemas:
            all_samples.append((plugin_name, schemas[:3]))

    print(f"\nTotal: {total_written} schemas written to {_OUTPUT_BASE}/")
    print("\nMCP prefix patterns (verified against api_requests_opus_monitor_cc_1776092124.jsonl):")
    for plugin_name, prefix in _MCP_PREFIXES.items():
        print(f"  {plugin_name}: {prefix}<tool_name>")

    print("\n--- Sample schemas (Opus spotcheck) ---")
    for plugin_name, samples in all_samples:
        print(f"\n[{plugin_name}]")
        for schema in samples:
            print(json.dumps(schema, indent=2))


# FUNCTIONS

# Ensure server venv exists with required packages; returns path to venv python3.
def _ensure_venv(plugin_name: str, venv_dir: str, server_project_dir: str) -> str:
    python_path = os.path.join(venv_dir, "bin", "python3")
    if not os.path.exists(python_path):
        print(f"[{plugin_name}] Bootstrapping venv at {venv_dir}...")
        req_path = os.path.join(server_project_dir, "requirements.txt")
        subprocess.run(["python3", "-m", "venv", venv_dir], check=True)
        if os.path.exists(req_path):
            subprocess.run([python_path, "-m", "pip", "install", "-q", "-r", req_path], check=True)
        print(f"[{plugin_name}] Venv ready.")
    return python_path


# Invoke server extraction in a clean subprocess. Returns list of Anthropic-format schema dicts.
def _extract_plugin_schemas(
    plugin_name: str, server_path: str, server_project_dir: str, venv_python: str
) -> list[dict]:
    prefix = _MCP_PREFIXES[plugin_name]
    result = subprocess.run(
        [venv_python, "-c", _HELPER_CODE, server_path, prefix],
        capture_output=True,
        text=True,
        cwd=server_project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Schema extraction failed for {plugin_name}:\n{result.stderr}")
    return json.loads(result.stdout)


# Write each schema as a separate JSON file; returns count of files written.
def _write_schemas(plugin_name: str, schemas: list[dict]) -> int:
    out_dir = _OUTPUT_BASE / plugin_name
    out_dir.mkdir(parents=True, exist_ok=True)
    for schema in schemas:
        tool_bare_name = schema["name"].split("__")[-1]
        out_path = out_dir / f"{tool_bare_name}.json"
        out_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    return len(schemas)


if __name__ == "__main__":
    extract_schemas_workflow()
