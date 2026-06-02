# Import the 'json' module to parse and serialize JSON data (used for tool arguments and responses)
import json

# Import the 'os' module to access environment variables and file system operations
import os

# Import the Groq API client — this is how we communicate with LLMs (Llama, Qwen, etc.)
from groq import Groq

# Import load_dotenv to read API keys and configuration from the .env file
from dotenv import load_dotenv

# Import the search function from rag_engine.py — used to query the vector database for team data
# Also import 'collection' (ChromaDB collection object) if needed for advanced queries
from rag_engine import search, collection

# Import GitHub helper functions from github_client.py — used to fetch contributor and commit data
# (fetch_contributors gets commit stats, fetch_commits retrieves commit history, summarize_commit creates summaries)
from github_client import fetch_contributors, fetch_commits, summarize_commit

# Import from reasoning_engine.py: reason() sends complex questions to the reasoning model,
# is_reasoning_question() detects if a question needs deep analysis (vs simple lookup)
from reasoning_engine import reason, is_reasoning_question

# Load environment variables from .env file into os.environ (contains GROQ_API_KEY, etc.)
load_dotenv()

# Initialize the Groq API client with the API key from the environment — this object is used throughout
# to make API calls to models like Llama 3.3 and Qwen. Called by: run() method in TeamLensAgent
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Tool definitions ──────────────────────────────────────────
# This is how we tell the LLM what tools exist and when to use them.
# Think of this like an API contract — the LLM reads these descriptions
# and decides which tool fits the user's question.
# In Java terms: this is like registering method signatures with metadata.
# Called by: run() method when sending messages to the Groq API

# A list of tool definitions that the LLM can choose from
# Each tool is a JSON object describing its name, purpose, and parameters
TOOLS = [
    # First tool: search_knowledge_base — retrieves relevant data from ChromaDB
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Search the TeamLens knowledge base for information about "
                "pull requests, Jira tickets, PagerDuty incidents, team health, "
                "burnout signals, blocked work, sprint velocity, and oncall burden. "
                "Use this for ALL questions about engineers by name — including "
                "comparisons ('who is better', 'compare X and Y'), burnout risk, "
                "workload, cycle time, carry-overs, and performance. "
                "NEVER use get_contributor_stats for engineer health or comparison questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # Required parameter: the search query (natural language)
                    "query": {
                        "type": "string",
                        "description": "Natural language search query"
                    },
                    # Optional parameter: filter results by GitHub, Jira, or PagerDuty
                    "source": {
                        "type": "string",
                        "enum": ["github", "jira", "pagerduty"],
                        "description": "Optional — filter by data source"
                    }
                },
                # Only 'query' is required; 'source' is optional
                "required": ["query"]
            }
        }
    },
    # Second tool: get_contributor_stats — fetches GitHub commit statistics
    {
        "type": "function",
        "function": {
            "name": "get_contributor_stats",
            "description": (
               "Get GitHub contributor statistics — total commits per engineer from a GitHub repo. "
                "ONLY use this for questions explicitly about GitHub commit counts or repository-level "
                "code contribution history. Do NOT use for engineer health, burnout, performance "
                "comparisons, workload analysis, or any question that can be answered from "
                "Jira or PagerDuty data. Requires a valid GitHub token to be configured."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # Required parameter: the GitHub repository owner (e.g., "microsoft")
                    "owner": {
                        "type": "string",
                        "description": "GitHub repo owner"
                    },
                    # Required parameter: the GitHub repository name (e.g., "vscode")
                    "repo": {
                        "type": "string",
                        "description": "GitHub repo name"
                    }
                },
                # Both owner and repo are required to fetch data
                "required": ["owner", "repo"]
            }
        }
    },
    # Third tool: get_sprint_summary — retrieves Jira sprint metrics
    {
        "type": "function",
        "function": {
            "name": "get_sprint_summary",
            "description": (
                "Get sprint velocity and health summary — completion rates, "
                "carry-over points, blocked tickets, and sprint sentiment. "
                "Use this for questions about delivery velocity or sprint health."
            ),
            "parameters": {
                "type": "object",
                # This tool takes no parameters — it returns data for the current sprint
                "properties": {},
                "required": []
            }
        }
    }
]  # End of TOOLS list — these are passed to the Groq API to enable the LLM to call functions


# ── Tool execution ────────────────────────────────────────────
# When the LLM decides to call a tool, this function actually runs it.
# The LLM tells us the tool name + arguments, we execute and return results.
# Called by: run() method in the ReACT loop when the LLM requests a tool

def execute_tool(tool_name, tool_args):
    """
    Runs the tool the LLM requested and returns results as a string.
    The LLM can only read text — so we convert everything to JSON string.
    
    Parameters:
      tool_name (str): The name of the tool to execute (e.g., "search_knowledge_base")
      tool_args (dict): The arguments passed by the LLM (e.g., {"query": "..."})
    
    Returns:
      str: The result as a string (LLM-readable format)
    """

    # Print a diagnostic message showing which tool is being called and with what arguments
    print(f"  → Agent calling tool: {tool_name}({tool_args})")

    # Route 1: Handle search_knowledge_base tool calls
    if tool_name == "search_knowledge_base":
        # Extract the search query from tool arguments
        query = tool_args["query"]
        
        # Extract the optional source filter (None if not provided)
        source = tool_args.get("source")  # optional filter
        
        # Call the search() function from rag_engine.py — returns up to 4 most relevant hits from ChromaDB
        hits = search(query, n_results=4, source_filter=source)

        # Format results as readable text for the LLM (it can't read raw JSON well)
        result = []
        
        # Iterate through each search result and format it with source label
        for hit in hits:
            result.append(
                f"[{hit['metadata']['source'].upper()}] {hit['text']}"
            )
        
        # Join all results with blank lines for readability and return to LLM
        return "\n\n".join(result)

    # Route 2: Handle get_contributor_stats tool calls
    elif tool_name == "get_contributor_stats":
        # Extract the GitHub repository owner from tool arguments
        owner = tool_args["owner"]
        
        # Extract the GitHub repository name from tool arguments
        repo = tool_args["repo"]
        
        # Call fetch_contributors() from github_client.py — retrieves commit stats for all engineers
        contributors = fetch_contributors(owner, repo)
        
        # Return only top 10 contributors as a formatted JSON string (readable for LLM)
        return json.dumps(contributors[:10], indent=2)

    # Route 3: Handle get_sprint_summary tool calls
    elif tool_name == "get_sprint_summary":
        # Open and read the mock Jira data file (simulating a Jira API call)
        with open("mock_data/jira_mock.json") as f:
            jira = json.load(f)
        
        # Extract the sprint health summary object from the mock data
        summary = jira["sprint_health_summary"]
        
        # Extract the team members list from the mock data
        team = jira["team_members"]
        
        # Return a formatted JSON string combining both sprint health and team load data
        return json.dumps({
            "sprint_health": summary,
            "team_load": team
        }, indent=2)

    # Fallback: handle unknown tool names
    else:
        # Return an error message if the tool name doesn't match any known tools
        return f"Unknown tool: {tool_name}"


# ── Agent class ───────────────────────────────────────────────
# This is the main orchestrator for the team health analysis agent.
# Called by: The main __main__ block at the bottom of this file

class TeamLensAgent:
    """
    The main agent class. Maintains conversation history and
    orchestrates the ReACT loop between Groq and our tools.
    """

    # Constructor — called when creating a new agent instance (e.g., TeamLensAgent())
    def __init__(self, owner="microsoft", repo="vscode"):
        # Store the GitHub repository owner (default: "microsoft")
        self.owner = owner
        
        # Store the GitHub repository name (default: "vscode")
        self.repo = repo

        # Initialize the conversation history — this is how the LLM remembers context
        # across multiple questions in a session.
        # In Java terms: think of this as a List<Message> that grows with every exchange.
        # The list stores dictionaries with role (system/user/assistant/tool) and content
        self.messages = [
            # System message: sets the LLM's role and instructions for this conversation
            {
                "role": "system",
               "content": (
                    "You are TeamLens, an AI analyst for engineering team health. "
                    "You have access to GitHub PR data, Jira sprint data, and "
                    "PagerDuty incident data for a platform engineering team. "
                    "Always use your tools to retrieve data before answering. "
                    "Always pass arguments as valid JSON. Be concise but specific. "
                    "Flag risks clearly.\n\n"
                    "TOOL ROUTING RULES — follow these exactly:\n"
                    "1. For ANY question about engineers by name — comparisons, burnout, "
                    "workload, risk, cycle time, carry-overs, performance — ALWAYS use "
                    "search_knowledge_base. Never use get_contributor_stats for these.\n"
                    "2. Only use get_contributor_stats when the user explicitly asks about "
                    "GitHub commit counts or repository contribution history AND a GitHub "
                    "token is available.\n"
                    "3. Use get_sprint_summary for questions about sprint velocity, "
                    "completion rates, or delivery health.\n"
                    "4. When comparing two engineers (e.g. 'who is better between X and Y'), "
                    "search for each engineer individually using search_knowledge_base, "
                    "then synthesize the results."
               )
            }
        ]

    # Main execution method — called for each user question
    # Called by: The main __main__ block for each question in the test suite
    def run(self, user_question):
        # Add the user's question to the message history
        # This ensures the LLM sees all context from this conversation
        self.messages.append({
            "role": "user",
            "content": user_question
        })

        # Print the question to stdout for debugging/visibility
        print(f"\nQuestion: {user_question}")
        # Print a visual separator line
        print("─" * 50)

        # ── Route to reasoning model if needed ──
        # This is the P4 concept — inference time scaling
        # Complex "why/analyze/root cause" questions get a reasoning model
        # Simple lookups stay on Llama 3.3 (fast + cheap)
        
        # Check if this question needs deep reasoning (calls is_reasoning_question from reasoning_engine.py)
        if is_reasoning_question(user_question):
            # Send the question to the reasoning model (calls reason() from reasoning_engine.py)
            result = reason(user_question)
            # Print the reasoning model's answer
            print(f"\nAnswer (via reasoning model): {result['answer']}\n")
            # Add the assistant's reasoning response to conversation history
            self.messages.append({
                "role": "assistant",
                "content": result["answer"]
            })
            # Return early — don't execute the ReACT loop for reasoning questions
            return result

        # ── Simple questions — full ReACT loop ──
        # This loop implements the ReACT pattern: Reason → Act → Observe → Repeat
        # The LLM can call tools multiple times and read their results before giving a final answer
        while True:

            # Step 1 (Reason): Call the LLM to think about the question and decide if tools are needed
            # This call uses the Groq API client initialized at the top of the file
            response = client.chat.completions.create(
                # Use Llama 3.3 70B — fast and capable for most tasks
                model="llama-3.3-70b-versatile",
                # Pass the entire conversation history (messages array)
                messages=self.messages,
                # Tell the LLM about available tools (the TOOLS list defined earlier)
                tools=TOOLS,
                # "auto" means the LLM decides whether to call tools or respond directly
                tool_choice="auto",
                # Cap the response at 1024 tokens to prevent excessive output
                max_tokens=1024
            )

            # Extract the message from the API response
            message = response.choices[0].message
            
            # Check if the LLM decided to call any tools
            has_tool_calls = bool(message.tool_calls)

            # Build an assistant message to add to conversation history
            # Include the LLM's reasoning (content) and any tool calls it made
            assistant_message = {"role": "assistant", "content": message.content or ""}
            # Only add tool_calls key if the LLM actually called tools
            if has_tool_calls:
                assistant_message["tool_calls"] = message.tool_calls
            # Add the assistant message to the conversation history
            self.messages.append(assistant_message)

            # Step 2 (Act): Execute any tools the LLM requested
            if has_tool_calls:
                # Iterate through each tool call the LLM made
                for tool_call in message.tool_calls:
                    # Extract the tool name (e.g., "search_knowledge_base")
                    tool_name = tool_call.function.name
                    # Parse the JSON arguments passed by the LLM
                    tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    # Execute the tool by calling execute_tool() and get the result
                    tool_result = execute_tool(tool_name, tool_args)

                    # Step 3 (Observe): Add the tool result to conversation history
                    # This is how the LLM sees what happened when it called the tool
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,  # Links this result back to the tool call
                        "content": tool_result
                    })
                # Loop continues — LLM reads tool results and decides its next action
                # It might: 1) call more tools, 2) ask for clarification, or 3) give final answer

            else:
                # Step 4 (Complete): No tool calls = LLM has enough info to answer
                # Extract the LLM's final answer
                final_answer = message.content
                # Print the final answer to stdout
                print(f"\nAnswer: {final_answer}\n")
                # Return the answer and exit the loop
                return {"answer": final_answer}

# ── Test it ───────────────────────────────────
# This section runs only when the script is executed directly (not imported)
if __name__ == "__main__":

        # Create a new TeamLensAgent instance for analyzing the Microsoft VSCode repository
        # This initializes the agent with owner="microsoft" and repo="vscode"
        agent = TeamLensAgent(owner="microsoft", repo="vscode")

        # Define a list of test questions — progressively more complex
        # These range from simple lookups to complex reasoning tasks
        questions = [
            "What is the current sprint completion rate?",  # Simple lookup
            "Is anyone on the team showing burnout signals?",  # Requires analysis
            "What should I discuss in my 1:1 with emily.zhang this week?",  # Reasoning question
        ]

        # Iterate through each test question and process it
        for question in questions:
            # Call the agent's run() method to process the question
            # This will either route to reasoning model or execute the ReACT loop
            agent.run(question)
            # Print a separator line to visually divide test outputs
            print("=" * 60)