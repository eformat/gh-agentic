import openai
import subprocess
import json
import os
import threading
import queue
import sys
import base64
import re
import requests
from rich import print

class GitHubAIAssistant:
    def __init__(self, openai_api_key, base_url, model, github_token, max_tokens):
        self.openai_api_key = openai_api_key
        self.base_url = base_url
        self.model = model
        self.github_token = github_token
        self.max_tokens = max_tokens
        self.mcp_process = None
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
    def start_mcp_server(self):
        # Start the MCP server process
        self.mcp_process = subprocess.Popen(
            ["podman", "run", "-i", "--rm", 
             "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={self.github_token}",
             "ghcr.io/github/github-mcp-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Start threads to handle I/O with the MCP server
        threading.Thread(target=self._read_from_mcp, daemon=True).start()
        threading.Thread(target=self._write_to_mcp, daemon=True).start()
        
    def _read_from_mcp(self):
        while self.mcp_process and self.mcp_process.poll() is None:
            line = self.mcp_process.stdout.readline()
            if line:
                self.output_queue.put(line)
    
    def _write_to_mcp(self):
        while self.mcp_process and self.mcp_process.poll() is None:
            try:
                message = self.input_queue.get(timeout=0.1)
                self.mcp_process.stdin.write(message + "\n")
                self.mcp_process.stdin.flush()
            except queue.Empty:
                pass
    
    def send_to_mcp(self, command):
        """Send a command to the MCP server"""
        self.input_queue.put(json.dumps(command))
        
        # Wait for response
        response = ""
        while True:
            try:
                line = self.output_queue.get(timeout=5)
                response += line
                if line.strip() and "}" in line:  # Simple check for JSON completion
                    break
            except queue.Empty:
                break
                
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"error": "🌴 Invalid JSON response", "raw": response}

    def decode_content(self, content, filename):
        """Decode base64 content if needed"""
        try:
            # Try to decode as base64 first
            decoded = base64.b64decode(content).decode('utf-8')
            return decoded
        except Exception:
            # If decoding fails, return original content
            return content

    def get_file_content(self, owner, repo, path, ref):
        """Get file content using GitHub MCP"""
        command = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_file_contents",
                "arguments": {
                    "owner": owner,
                    "repo": repo,
                    "path": path,
                    "ref": ref
                }
            }
        }
        return self.send_to_mcp(command)
    
    def _parse_openai_response(self, content):
        """Helper method to parse and validate OpenAI response"""
        return f"{content}\n"

    def analyze_code_with_openai(self, file_contents, ticket_details=None):
        """Analyze code using OpenAI API with chunking for large requests"""
        client = openai.OpenAI(api_key=self.openai_api_key, base_url=self.base_url)

        # Sort files by size to prioritize smaller files in first chunk
        sorted_files = sorted(file_contents.items(), key=lambda x: len(x[1]['content']))
        
        # Estimate base prompt token count
        base_prompt = "You are an AI assistant that is expert at summarizing code:\n\n"
        chunk_prompt_parts = [base_prompt]
        
        # Instructions prompt
        instructions_prompt = (
            "Use the following principles to generate the code summary from the provided file content\n"
            "- Concisely summarize what the code is doing.\n"
            "- Include small code snippets to create a comprehensive summary\n"
            "Return the generated summary as follows:\n"
            "[Start Summary]\n"
            "<insert summary here>"
            "[End Summary]\n"
        )

        for filename, file_data in sorted_files:
            file_type = filename.split('.')[-1].lower()
            chunk_prompt_parts.append(f"File: {filename}\n\n```{file_type}\n{file_data['content']}\n```\n\n")
            chunk_prompt_parts.append(instructions_prompt)
            chunk_prompt = "".join(chunk_prompt_parts)
            chunk_review = []
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    temperature=0.2,
                    max_tokens=self.max_tokens,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a code review assistant. Format your response as valid markdown."
                            )
                        },
                        {"role": "user", "content": chunk_prompt}
                    ]
                )
                
                chunk_review = self._parse_openai_response(response.choices[0].message.content)

            except Exception as e:
                print(f"🌴 Error processing chunk: {e}")

            return chunk_review

    def stop(self):
        """Stop the MCP server process"""
        if self.mcp_process:
            self.mcp_process.terminate()
            try:
                self.mcp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.mcp_process.kill()

# Example usage
if __name__ == "__main__":
    # Get environment variables safely with default values
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("BASE_URL")
    model = os.environ.get("MODEL")
    github_token = os.environ.get("GITHUB_TOKEN")
    max_tokens = os.environ.get("MAX_TOKENS")
    
    # Validate required environment variables
    if not openai_api_key or not github_token or not base_url or not max_tokens or not model:
        print("🌴 Error: OPENAI_API_KEY, BASE_URL, MODEL, MAX_TOKENS, GITHUB_TOKEN environment variables must be set")
        sys.exit(1)
    
    try:
        assistant = GitHubAIAssistant(
            openai_api_key=openai_api_key,
            base_url=base_url,
            model=model,
            github_token=github_token,
            max_tokens=max_tokens
        )
        
        print("🌴 Starting MCP server...")
        assistant.start_mcp_server()
        
        # Example: Review a PR
        # Allow command line arguments for owner/repo/PR
        owner = sys.argv[1] if len(sys.argv) > 1 else "eformat"
        repo = sys.argv[2] if len(sys.argv) > 2 else "welcome"
        filename = sys.argv[3] if len(sys.argv) > 3 else "README.md"
        ref = sys.argv[3] if len(sys.argv) > 4 else "master"
        
        print(f"🌴 Get file content {filename} in {owner}/{repo} for {ref}...")
        # def get_file_content(self, owner, repo, path, ref):
        file_content_response = assistant.get_file_content(owner, repo, filename, ref)
        #print(json.dumps(file_content_response, indent=2))

        # Extract content from the nested response
        file_content = None
        file_contents = {}
        if isinstance(file_content_response, dict) and "result" in file_content_response:
            if "content" in file_content_response["result"] and isinstance(file_content_response["result"]["content"], list):
                for item in file_content_response["result"]["content"]:
                    if item.get("type") == "text" and "text" in item:
                        try:
                            content_obj = json.loads(item["text"])
                            if "content" in content_obj:
                                # Decode the content if it's base64 encoded
                                file_content = assistant.decode_content(content_obj["content"], filename)
                                file_contents[filename] = {
                                    "content": file_content
                                }
                                break
                        except json.JSONDecodeError:
                            pass
        
        if not file_content:
            print(f"🌴 Warning: Could not extract content for {filename}, skipping")
        
        #print(file_contents)
        print("🌴 Analyze code...\n")
        analysis = assistant.analyze_code_with_openai(file_contents, None)
        print(analysis)

    except Exception as e:
        print(f"🌴 Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'assistant' in locals():
            print("🌴 Stopping MCP server...")
            assistant.stop()