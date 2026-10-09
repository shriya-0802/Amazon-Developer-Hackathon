# 🧠 LifeSync — AI-Powered Proactive Personal Operations Center

> **An Alexa+ MCP Server that doesn't wait for commands — it anticipates your needs.**
Link-> https://lifesync-lxks.onrender.com/

## 🎯 What is LifeSync?

LifeSync is an **agentic MCP server** for Alexa+ that acts as your proactive personal operations center. Unlike traditional voice assistants that respond to commands, LifeSync:

- **Orchestrates autonomously** across calendar, email, tasks, shopping, fitness, and context services
- **Maintains persistent memory** across sessions using a knowledge graph
- **Acts proactively** — notices patterns and suggests/executes before you ask
- **Delivers rich experiences** via MCP Apps (cards, carousels, interactive elements)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                  Alexa+ / Web UI                │
│              (Simulated Experience)              │
└─────────────────┬───────────────────────────────┘
                  │ Streamable HTTP
┌─────────────────▼───────────────────────────────┐
│            LifeSync MCP Server                   │
│         (Python + FastAPI, spec 2025-11-25)      │
├──────────────────────────────────────────────────┤
│  Agent Orchestrator (AWS Strands SDK)            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Calendar │ │  Email   │ │  Tasks   │        │
│  │  Agent   │ │  Agent   │ │  Agent   │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Shopping │ │ Fitness  │ │ Context  │        │
│  │  Agent   │ │  Agent   │ │  Agent   │        │
│  └──────────┘ └──────────┘ └──────────┘        │
├──────────────────────────────────────────────────┤
│  Memory Layer (Knowledge Graph + DynamoDB)       │
├──────────────────────────────────────────────────┤
│  AWS: Bedrock (Claude) │ AgentCore │ Lambda     │
└──────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for web simulation)
- AWS Account with Bedrock access
- AWS CLI configured

### Server Setup
```bash
cd server
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your AWS credentials
python main.py
```

### Web Simulation
```bash
cd web
npm install
npm run dev
```

## 📦 Project Structure

```
lifesync/
├── server/                    # MCP Server (Python)
│   ├── main.py               # FastAPI + MCP entry point
│   ├── mcp_handler.py        # MCP protocol implementation
│   ├── agents/               # Agent implementations
│   │   ├── orchestrator.py   # Multi-agent orchestrator
│   │   ├── calendar_agent.py # Calendar management
│   │   ├── email_agent.py    # Email intelligence
│   │   ├── task_agent.py     # Task tracking
│   │   ├── shopping_agent.py # Smart shopping
│   │   ├── fitness_agent.py  # Fitness tracking
│   │   └── context_agent.py  # Weather, transit, news
│   ├── memory/               # Persistent memory
│   │   ├── knowledge_graph.py
│   │   └── session_store.py
│   └── requirements.txt
├── web/                       # Web Simulation UI
│   ├── index.html
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   └── app.js
│   └── package.json
├── lifesync-mcp-toolkit/      # Open Source Library
│   ├── README.md
│   ├── LICENSE
│   ├── setup.py
│   └── lifesync_toolkit/
└── README.md
```

## 🏆 Hackathon Tracks

- **Primary Track:** Alexa+ (MCP Server + Simulated Experience)
- **Mini Challenge:** AWS Builder (Bedrock + AgentCore + Strands SDK)
- **Mini Challenge:** Open Source (`lifesync-mcp-toolkit`)

## 🔧 Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | Python, FastAPI, MCP SDK |
| AI/LLM | AWS Bedrock (Claude 4 Sonnet) |
| Agent Framework | AWS Strands SDK, AgentCore |
| Memory | DynamoDB, In-memory Knowledge Graph |
| Serverless | AWS Lambda (proactive triggers) |
| Web Simulation | Vite, Vanilla JS, CSS |

