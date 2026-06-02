# Import the 'os' module to access environment variables (like API keys)
import os

# Import the 're' (regex) module to parse thinking tags from model responses
import re

# Import the Groq API client library — this is what we use to call the AI models
from groq import Groq

# Import load_dotenv to read the .env file and populate environment variables
from dotenv import load_dotenv

# Import the search function from rag_engine.py — used to retrieve context from ChromaDB
from rag_engine import search

# Load environment variables from the .env file (contains GROQ_API_KEY)
load_dotenv()

# Initialize a Groq client with the API key from the environment — this is our connection to the reasoning model
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Question classifier ───────────────────────────────────────
# Decides whether a question needs deep reasoning or a fast lookup.
# This is the router — the brain that picks the right model.

# A list of keywords that signal the question needs deep reasoning (not just a simple lookup)
# These words indicate the user is asking for analysis, explanation, or prediction
REASONING_TRIGGERS = [
    "why", "what caused", "root cause", "explain", "how did",
    "what led to", "analyze", "analysis", "pattern", "trend",
    "predict", "what will", "what would", "risk", "should i",
    "recommend", "what's behind", "investigate"
]

def is_reasoning_question(question):
    """
    Returns True if the question needs deep reasoning.
    Simple keyword match — good enough for a capstone project.
    In production you'd use a classifier model for this.
    """
    # Convert the question to lowercase so keyword matching is case-insensitive
    question_lower = question.lower()
    
    # Use 'any()' to check if ANY of the reasoning trigger keywords appear in the question
    # If at least one trigger keyword is found, return True; otherwise return False
    return any(trigger in question_lower for trigger in REASONING_TRIGGERS)


# ── Context builder ───────────────────────────────────────────
# Before sending to the reasoning model, we retrieve ALL relevant
# context from ChromaDB across all three sources.
# More context = better reasoning.

def build_context_for_reasoning(question):
    """
    Pulls relevant chunks from all three data sources.
    Combines them into a single rich context block for the reasoning model.
    """
    # Query GitHub data: retrieve 3 most relevant pull request chunks for the question
    github_hits = search(question, n_results=3, source_filter="github")
    
    # Query Jira data: retrieve 4 most relevant ticket chunks for the question
    jira_hits = search(question, n_results=4, source_filter="jira")
    
    # Query PagerDuty data: retrieve 4 most relevant incident chunks for the question
    pd_hits = search(question, n_results=4, source_filter="pagerduty")

    # Initialize an empty list to accumulate context parts that will be joined together
    context_parts = []

    # If GitHub search returned any results, add them to the context with a header
    if github_hits:
        context_parts.append("── GitHub Data ──")
        # Add each individual GitHub hit's text to the context
        for hit in github_hits:
            context_parts.append(hit["text"])

    # If Jira search returned any results, add them to the context with a header
    if jira_hits:
        context_parts.append("\n── Jira Data ──")
        # Add each individual Jira hit's text to the context
        for hit in jira_hits:
            context_parts.append(hit["text"])

    # If PagerDuty search returned any results, add them to the context with a header
    if pd_hits:
        context_parts.append("\n── PagerDuty Data ──")
        # Add each individual PagerDuty hit's text to the context
        for hit in pd_hits:
            context_parts.append(hit["text"])

    # Join all context parts together with newlines and return as a single string
    return "\n".join(context_parts)


# ── Reasoning model caller ────────────────────────────────────

def call_reasoning_model(question, context):
    """
    Sends the question + context to DeepSeek R1.

    Key difference from regular model:
    - System prompt explicitly asks for step-by-step thinking
    - We use DeepSeek R1 which has a built-in <think> scratchpad
    - Temperature 0.6 gives it room to explore different angles
      (vs 0 which would make it deterministic/shallow)
    """

    # Define the system prompt that instructs the model on its role and reasoning approach
    # This prompt tells the model to act as a senior engineering leader and to look for patterns
    system_prompt = """You are a senior engineering leader and team health analyst.
You have been given data from GitHub, Jira, and PagerDuty about an engineering team.

When analyzing, always:
1. Look for PATTERNS across multiple data sources, not just individual data points
2. Distinguish between SYMPTOMS (what you see) and ROOT CAUSES (why it's happening). 
3. Consider the HUMAN impact — workload, stress, blocked engineers. Don't include this in the response; use this for THINKING only
4. Give SPECIFIC, ACTIONABLE recommendations with names and ticket numbers.
5. Flag RISKS that aren't yet visible but are likely based on current trends
6. Summarize your thinkings in a crips, clear and bullet-pointed final answer.
7. The final answers should be at the start of your response, like a tl;dr.
8. Overall, the response should be concise and crisp. use bullet points and avoid long paragraphs. bolding or ALL CAPS for emphasis is encouraged.

Think carefully and thoroughly before concluding."""

    # Build the user prompt by combining the context and the original question
    user_prompt = f"""Here is the team data:

{context}

Question: {question}

Think step by step through the data before answering."""

    # Print a message to indicate we're about to call the reasoning model
    print("  → Routing to reasoning model (DeepSeek R1)...")

    # Call the Groq API with the specified model and parameters
    response = client.chat.completions.create(
        # Use the Qwen3 32B model (a powerful reasoning model)
        model="qwen/qwen3-32b",
        
        # Pass the system and user messages in the correct format
        messages=[
            # The system message sets the model's behavior and role
            {"role": "system", "content": system_prompt},
            # The user message contains the actual question and context
            {"role": "user", "content": user_prompt}
        ],
        
        # Temperature 0.6 allows the model to be creative while staying focused
        # (0 = deterministic, 1 = highly creative)
        temperature=0.6,
        
        # Maximum 2048 tokens in the response (prevents overly long outputs)
        max_tokens=2048,
        # reasoning_format="hidden" hides the <think> block from final output
        # We use "raw" so you can SEE the thinking during development
    )

    # Extract the full response text from the API response object
    full_response = response.choices[0].message.content

    # Use regex to search for the <think>...</think> tags in the response
    # These tags contain the model's internal reasoning/chain-of-thought
    think_match = re.search(r'<think>(.*?)</think>', full_response, re.DOTALL)
    
    # If the think tags were found, extract the content between them; otherwise use empty string
    thinking = think_match.group(1).strip() if think_match else ""
    
    # Remove the <think>...</think> tags from the response to get just the final answer
    answer = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL).strip()

    # Fallback: if no answer text remains after removing think tags, use the entire response
    if not answer:
        answer = full_response.strip()

    # Return a dictionary with the answer, thinking process, and model name used
    return {
        "answer": answer,
        "thinking": thinking,
        "model": "qwen/qwen3-32b"
    }


# ── Main entry point ──────────────────────────────────────────

def reason(question):
    """
    Public function the agent will call for reasoning questions.
    Builds context, calls DeepSeek R1, returns structured result.
    """
    # Print status message indicating we're starting the reasoning process
    print(f"\n  [Reasoning engine] Building context for: '{question}'")
    
    # Retrieve relevant context from ChromaDB by searching across all three data sources
    context = build_context_for_reasoning(question)
    
    # Send the question and context to the reasoning model and get back an answer
    result = call_reasoning_model(question, context)
    
    # Return the structured result containing the answer, thinking, and model name
    return result


# ── Test it ───────────────────────────────────────────────────
# This section only runs when the script is executed directly (not imported)
if __name__ == "__main__":

    # Define a list of test questions to demonstrate the reasoning engine's capabilities
    test_questions = [
        "Why did platform reliability degrade in February?",
        "What is the root cause of Emily's carry-over pattern?",
        "Should I be worried about burnout on this team?",
    ]

    # Iterate through each test question and process it
    for question in test_questions:
        # Print a separator line to make the output more readable
        print(f"\n{'='*60}")
        
        # Print the current question being processed
        print(f"Question: {question}")
        
        # Print another separator line
        print('='*60)

        # Call the reason() function to get the result for this question
        result = reason(question)

        # If the result contains thinking output (the model's internal reasoning)
        if result["thinking"]:
            # Print a header indicating this is the chain-of-thought
            print(f"\n[Chain of thought — DeepSeek R1 thinking out loud]")
            
            # Extract the first 500 characters of the thinking to avoid flooding the terminal
            thinking_preview = result["thinking"][:500]
            
            # Print the thinking preview with an ellipsis to show it's truncated
            print(f"{thinking_preview}...")

        # Print a header for the final answer section
        print(f"\n[Final answer]")
        
        # Print the final answer provided by the model
        print(result["answer"])