import chromadb
import json
import os
from sentence_transformers import SentenceTransformer

# Load the embedding model — this runs locally on your machine
# First run downloads it (~80MB), subsequent runs load from cache
print("Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded.")

# Initialize ChromaDB — stores data in a local folder called 'vectorstore'
# Think of this like creating a local database file (like SQLite)
client = chromadb.PersistentClient(path="./vectorstore")

# A Collection in ChromaDB is like a table in a relational database
# get_or_create means: use it if it exists, create it if it doesn't
collection = client.get_or_create_collection(
    name="teamlens",
    metadata={"hnsw:space": "cosine"}  # use cosine similarity for search
)


def embed(text):
    """
    Converts a string into a vector using the local model.
    Returns a plain Python list (ChromaDB expects list, not numpy array)
    """
    return model.encode(text).tolist()


def chunk_github_prs(prs):
    """
    Converts PR data into text chunks ready for embedding.

    This is the 'chunking' step of RAG — breaking data into
    meaningful pieces. Each PR becomes one chunk.

    Think of each chunk as a row you're inserting into the vector DB.
    """
    chunks = []
    for pr in prs:
        # Build a natural language description of the PR
        # The richer this text, the better the AI can reason about it
        cycle_info = f"cycle time {pr.get('cycle_time_days')} days" if pr.get('cycle_time_days') else "not merged"

        text = (
            f"PR #{pr['number']} by {pr['author']}: {pr['title']}. "
            f"Status: {cycle_info}. "
            f"Reviewers: {', '.join(pr.get('reviewers', [])) or 'none assigned'}. "
            f"Labels: {', '.join(pr.get('labels', [])) or 'none'}. "
            f"Created: {pr['created_at'][:10]}."
        )

        chunks.append({
            "id": f"pr-{pr['number']}",
            "text": text,
            "metadata": {
                "source": "github",
                "type": "pull_request",
                "author": pr["author"],
                "cycle_time_days": str(pr.get("cycle_time_days") or ""),
            }
        })
    return chunks


def chunk_jira_tickets(jira_data):
    """
    Converts Jira tickets into text chunks.
    We pull from both sprints in the mock data.
    """
    chunks = []
    for sprint in jira_data["sprints"]:
        for ticket in sprint["tickets"]:

            # Include blocker info if it exists — key signal for team health
            blocker_info = f"Blocked for {ticket['blocked_days']} days due to: {ticket['blocker_reason']}." if ticket['blocked_days'] > 0 else "Not blocked."

            # Include latest comment for richer context
            latest_comment = ""
            if ticket["comments"]:
                last = ticket["comments"][-1]
                latest_comment = f"Latest comment by {last['author']}: {last['body']}"

            text = (
                f"Jira ticket {ticket['id']}: {ticket['title']}. "
                f"Assigned to {ticket['assignee']}. "
                f"Priority: {ticket['priority']}. "
                f"Status: {ticket['status']}. "
                f"Story points: {ticket['story_points']}. "
                f"Sprint: {sprint['name']}. "
                f"{blocker_info} "
                f"{latest_comment}"
            )

            chunks.append({
                "id": f"jira-{ticket['id']}",
                "text": text,
                "metadata": {
                    "source": "jira",
                    "type": "ticket",
                    "assignee": ticket["assignee"],
                    "priority": ticket["priority"],
                    "status": ticket["status"],
                    "sprint": sprint["id"],
                }
            })
    return chunks


def chunk_pagerduty_incidents(pd_data):
    """
    Converts PagerDuty incidents into text chunks.
    Incidents are the richest signal for burnout and reliability analysis.
    """
    chunks = []
    for incident in pd_data["incidents"]:

        after_hours_flag = "This was an after-hours page." if incident["was_after_hours"] else ""
        escalated_flag = f"Escalated because: {incident['escalation_reason']}." if incident["escalated"] else ""

        text = (
            f"Incident {incident['id']}: {incident['title']}. "
            f"Severity: {incident['severity']}. "
            f"On-call responder: {incident['oncall_primary']}. "
            f"Time to resolve: {incident['ttr_minutes']} minutes. "
            f"Root cause: {incident['root_cause']}. "
            f"Customer impact: {incident['customer_impact']}. "
            f"{after_hours_flag} "
            f"{escalated_flag} "
            f"Action items: {'; '.join(incident['action_items'])}."
        )

        chunks.append({
            "id": f"pd-{incident['id']}",
            "text": text,
            "metadata": {
                "source": "pagerduty",
                "type": "incident",
                "severity": incident["severity"],
                "oncall": incident["oncall_primary"],
                "after_hours": str(incident["was_after_hours"]),
                "ttr_minutes": str(incident["ttr_minutes"]),
            }
        })
    return chunks


def ingest_all(prs, jira_data, pd_data):
    """
    Master function — chunks all data sources and loads into ChromaDB.
    This is the 'indexing' step of RAG.
    """
    all_chunks = []
    all_chunks.extend(chunk_github_prs(prs))
    all_chunks.extend(chunk_jira_tickets(jira_data))
    all_chunks.extend(chunk_pagerduty_incidents(pd_data))

    print(f"\nIngesting {len(all_chunks)} chunks into ChromaDB...")

    # Process in batches of 50 — good practice for large datasets
    batch_size = 50
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]

        ids = [c["id"] for c in batch]
        texts = [c["text"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        # embed() converts each text to a vector
        embeddings = [embed(t) for t in texts]

        # upsert = insert if new, update if exists (like merge in SQL)
        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )

        print(f"  Ingested chunks {i+1} to {min(i+batch_size, len(all_chunks))}")

    print(f"Done. {collection.count()} chunks stored in ChromaDB.")


def search(query, n_results=5, source_filter=None):
    """
    Searches the vector store for chunks relevant to a query.
    This is the 'retrieval' step of RAG.

    source_filter: optionally filter by 'github', 'jira', or 'pagerduty'
    """
    query_vector = embed(query)

    # Build optional filter — only return chunks from a specific source
    where_clause = {"source": source_filter} if source_filter else None

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        where=where_clause
    )

    # Reformat results into a clean list of dicts
    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": round(results["distances"][0][i], 4)
            # distance: 0 = identical, 1 = completely different
            # lower is better
        })

    return hits


# ── Test it ───────────────────────────────────────────────
if __name__ == "__main__":
    from github_client import fetch_pull_requests, summarize_pr, compute_pr_cycle_time

    # Load GitHub data
    print("Fetching GitHub data...")
    raw_prs = fetch_pull_requests("microsoft", "vscode", max_pages=2)
    prs = [summarize_pr(pr) for pr in raw_prs]
    for pr in prs:
        pr["cycle_time_days"] = compute_pr_cycle_time(pr)

    # Load mock data
    print("Loading mock Jira and PagerDuty data...")
    with open("mock_data/jira_mock.json") as f:
        jira_data = json.load(f)
    with open("mock_data/pagerduty_mock.json") as f:
        pd_data = json.load(f)

    # Ingest everything
    ingest_all(prs, jira_data, pd_data)

    # Test some searches
    print("\n── Search tests ────────────────────────────────")

    test_queries = [
        "who has the most after hours incidents?",
        "which tickets are blocked?",
        "slowest pull requests",
        "burnout risk on the team",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        hits = search(query, n_results=3)
        for hit in hits:
            print(f"  [{hit['metadata']['source']}] (dist={hit['distance']}) {hit['text'][:100]}...")