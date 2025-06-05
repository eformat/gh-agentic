# gh-agentic

Demo for analyzing and summarizing code. This uses [github mcp server](https://github.com/github/github-mcp-server) in a container.

Pre-requisites

- podman
- github token

Setup

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Environment

```bash
export OPENAI_API_KEY=fake  # api key
export BASE_URL=http://localhost:8080/v1  # openai model
export MODEL=Llama-3.2-3B-Instruct-Q8_0.gguf  # model name
export GITHUB_TOKEN=ghp_your_token  # github token
export GITHUB_TOOLSETS=all # all,repos,issues,pull_requests,code_security,experiments
export MAX_TOKENS=512  # max generated tokens
```

Run - analyze some github code

```bash
# https://github.com/eformat/welcome/blob/master/README.md

python demo.py
```

```bash
# https://github.com/noelo/llama-stack-poc/blob/main/llamastack-noc-stack/llamastack-noc-stack-run.yaml

python demo.py noelo llama-stack-poc llamastack-noc-stack/llamastack-noc-stack-run.yaml main
```

Example output

```bash
((venv) ) virt:.../gh-agentic $ python demo.py noelo llama-stack-poc llamastack-noc-stack/llamastack-noc-stack-run.yaml main
🌴 Starting MCP server...
🌴 Get file content llamastack-noc-stack/llamastack-noc-stack-run.yaml in noelo/llama-stack-poc for llamastack-noc-stack/llamastack-noc-stack-run.yaml...
🌴 Analyze code...

[Start Summary]
This YAML file defines a container image for a LlamaStack application, which is a framework for building and deploying large language models. The code sets up various providers, 
models, and tools for inference, safety, agents, and more.

### Providers

The code defines several providers, which are responsible for interacting with external services or data sources. Here are a few examples:

* `vllm`: a remote provider for the VLLM (Vocabulary-based Large Language Model) model, which is used for inference and safety checks.
```yaml
- provider_id: vllm
  provider_type: remote::vllm
  config:
    url: ${env.VLLM_URL}
    max_tokens: ${env.VLLM_MAX_TOKENS:4096}
    api_token: ${env.VLLM_API_TOKEN:fake}

* `sentence-transformers`: an inline provider for the Sentence Transformers library, which is used for embedding and vector operations.

- provider_id: sentence-transformers
  provider_type: inline::sentence-transformers
  config: {}

### Models

The code defines two models:

* `vllm`: a metadata-only model for the VLLM model, which is used for inference and safety checks.

- metadata: {}
  model_id: ${env.INFERENCE_MODEL}
  provider_id: vllm
  model_type: llm

* `all-MiniLM-L6-v2`: an embedding model for the Sentence Transformers library, which is used for vector operations.

- metadata:
    embedding_dimension: 384
  model_id: all-MiniLM-L6-v2
  provider_id: sentence-transformers
  model_type: embedding

### Tool Groups

The code defines a tool group for testing, which uses the Model Context Protocol (MCP) to interact with the model.

- toolgroup_id: mcp::testtool
  provider_id: model-context-protocol
  mcp_endpoint:
    uri: "http://127.0.0.1:8888/sse"

[End Summary]

🌴 Stopping MCP server...
```
