import google.generativeai as genai
import os
import requests
from dotenv import load_dotenv
 
load_dotenv()
 
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
 
MCP_URL = "http://localhost:3000/ask"
 
 
# Architecture
# User → Gemini (LLM) → GENERATES_QUERY -> MCP Server (Node.js) → EXECUTES THE QUERY  → GCP API → Response to LLM
 
def generate_gcloud_command(question):
    """
    Use Gemini to generate a valid gcloud command for the question.
    """
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = f"""
    You are an expert in Google Cloud Platform CLI.
    Convert the following natural language question into a valid gcloud CLI command.
    - Always include --format=json for structured output.
    - Do NOT include destructive commands (like delete, remove).
    - Example: "List all active VMs" -> gcloud compute instances list --format=json
    Question: {question}
    Return only the command without any extra text.
    """
    prompt1= f"""
    You are a GCP command generator. Generate a single valid gcloud command for the user question.
    Follow these rules strictly:
    1. Use the correct gcloud CLI syntax.
    2. Use appropriate filters for accuracy (e.g., status=IN_USE for used IPs, status=RESERVED for unused IPs).
    3. Do NOT include delete, create, or modify operations. Only read/list commands.
    4. Always include `--format=json` at the end for machine-readable output.
    5. Output ONLY the command, nothing else.
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
    3. Format response for user.
    """
 
    command = generate_gcloud_command(question)
    print(f"Generated Command: {command}")
 
    mcp_result = ask_mcp(command)
 
    # Build summary prompt for final answer
    prompt = f"""
    Question: {question}
    GCP Command: {command}
    Raw Output: {mcp_result.get('raw')}
 
    Summarize the above result into a clear, concise human-readable answer for the user.
    """
 
    model = genai.GenerativeModel("gemini-1.5-pro")
    resp = model.generate_content(prompt)
    return resp.text
 
 
if __name__ == "__main__":
 
    while True:
        q=input("\nEnter the Question: ")
        print("A:", ask_gemini(q))
        print("*************************************************************************")
       
 