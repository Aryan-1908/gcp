import google.generativeai as genai
import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MCP_URL = "http://localhost:3000/ask"

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "gcp_logs.jsonl")

os.makedirs(LOG_DIR, exist_ok=True)

def save_log(question, command, mcp_result):
    """
    Save logs of question, command, and raw MCP output into a JSONL file.
    Each line is one JSON object for easy parsing later.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "command": command,
        "raw_output": mcp_result.get("raw") if isinstance(mcp_result, dict) else str(mcp_result),
        "Error"     : mcp_result.get('error') or mcp_result.get('stderr')
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    with open("logs/gcp_logs.log", "a", encoding="utf-8") as f:
        f.write("\n" + "="*60 + "\n")
        f.write(f"Timestamp : {datetime.now().isoformat()}\n")
        f.write(f"Question  : {question}\n")
        f.write(f"Command   : {command}\n")
        f.write(f"Raw Output: {mcp_result.get('raw')}\n")
        f.write(f"Error     : {mcp_result.get('error') or mcp_result.get('stderr')}\n")


def generate_gcloud_command(question):
    """
    Use Gemini to generate a valid gcloud command for the question.
    """
    model = genai.GenerativeModel("gemini-1.5-pro")

    # prompt = f"""
    # You are an expert in Google Cloud Platform CLI.
    # Convert the following natural language question into a valid gcloud CLI command.
    # - Always include --format=json for structured output.
    # - Do NOT include destructive commands (like delete, remove).
    # - Example: "List all active VMs" -> gcloud compute instances list --format=json
    # Question: {question}
    # Return only the command without any extra text.
    # """

    prompt = f"""
        You are an expert in Google Cloud Platform CLI.
        Convert the following natural language question into exactly ONE valid gcloud CLI command.

        Rules:
        - Always include --format=json for structured output.
        - Do NOT include destructive commands (delete, remove, stop, terminate).
        - If the exact data is not available in a single command, generate the closest valid gcloud command with the right filter.
        - Do NOT include --project or --zone unless explicitly mentioned in the question (defaults are already configured).
        - Use official gcloud CLI syntax only.
        - Return ONLY the gcloud command without explanations or extra text.

        Examples:
        Question: "List all active VMs"
        Answer: gcloud compute instances list --filter="status=RUNNING" --format=json

        Question: "Show all storage buckets"
        Answer: gcloud storage buckets list --format=json

        Question: "Get IAM roles"
        Answer: gcloud iam roles list --format=json

        Question: "List all unused IP addresses"
        Answer: gcloud compute addresses list --filter="status=RESERVED" --format=json

        Question: "List all used IP addresses"
        Answer: gcloud compute addresses list --filter="status=IN_USE" --format=json

        Now convert:
        Question: {question}

        """
    response = model.generate_content(prompt)
    return response.text.strip()


def ask_mcp(command):
    """
    Sends the gcloud command to MCP for execution.
    """
    payload = {"input": command}
    try:
        response = requests.post(MCP_URL, json=payload)
        if response.status_code == 200:
            return response.json()
        return {"error": f"MCP error: {response.status_code}, {response.text}"}
    except Exception as e:
        return {"error": str(e)}


def ask_gemini(question):
    """
    End-to-end process:
    1. Convert question to gcloud command.
    2. Execute via MCP.
    3. Save logs (backend only).
    4. Format response for user.
    """
    command = generate_gcloud_command(question)
    mcp_result = ask_mcp(command)

    # Extract raw/stdout and error/stderr if available
    raw_output = mcp_result.get("raw")
    error_output = mcp_result.get("error") or mcp_result.get("stderr")

    # Save raw logs for audit/debug (not shown to frontend)
    save_log(question, command, mcp_result)

    # Build summary prompt for final answer

    if error_output:
        prompt = f"""
        Question: {question}
        GCP Command: {command}
        Error Output: {error_output}

        The command failed. Summarize the error in simple language for the user,
        and suggest what they need to fix (e.g., missing flags, required parameters).
        """
    else:
        prompt = f"""
        Question: {question}
        GCP Command: {command}
        Raw Output: {mcp_result.get('raw')}
        Summarize the above result into a clear, concise human-readable answer for the user.
        """

    model = genai.GenerativeModel("gemini-1.5-pro")
    resp = model.generate_content(prompt)

    return command, mcp_result, resp.text
