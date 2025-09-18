
import os
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AzureAISearchTool
from azure.identity import DefaultAzureCredential
from iam_observability import log_step
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

load_dotenv()

class IAMAssistant:
    """IAM Assistant with live observability for queries."""

    def __init__(self):
        print("🔧 Initializing IAM Assistant...")
        self.project_client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=os.environ["AIPROJECT_CONNECTION_STRING"],
        )

        conn_list = self.project_client.connections.list()
        conn_id = next(
            (c.id for c in conn_list if c.connection_type == "CognitiveSearch"), None
        )
        if not conn_id:
            raise RuntimeError("No Cognitive Search connection found for IAM documents.")

        self.ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="iam-docs-rag")

        self.iam_agent = self.project_client.agents.create_agent(
            model="gpt-4.1-nano",
            name="IAM Assistant",
            instructions=
            """
           You are an expert assistant for Identity and Access Management in Entra ID.
            You should ONLY answer questions using the provided RAG documentation (iam-docs-rag).

Rules:
1. Search the documentation using the AI search tool.
2. Do NOT use any external sources (web, internet, etc.).
3. If the documentation does not contain relevant information, reply:
   "I don't know the answer to that. My responses are based solely on the IAM documentation."
4. Provide clear, concise answers only from the documentation.
5. Never guess or fabricate information.
            """,
            tools=self.ai_search.definitions,
            tool_resources=self.ai_search.resources,
        )

        self.thread = self.project_client.agents.create_thread()
        log_step("IAM Assistant initialized")

     # ------------------------
    # Detection helpers
    # ------------------------
    def infer_intent(self, query: str) -> str:
        q = query.lower()
        if q.startswith("how to") or "what is" in q or "steps to" in q:
            return "informational_query"
        return "unknown"

    def infer_system(self, query: str) -> str:
        q = query.lower()
        systems = {
            "entra": "Entra ID",
            "microsoft 365": "Entra ID",
            "azure ad": "Entra ID",
            "active directory": "Active Directory",
            "ad ": "Active Directory",
            "okta": "Okta",
            "pingone": "PingOne",
            "auth0": "Auth0",
            "google workspace": "Google Workspace",
            "onelogin": "OneLogin",
            "oracle identity": "Oracle Identity Cloud"
        }
        for keyword, name in systems.items():
            if keyword in q:
                return name
        return "Unknown"

    def detect_operation(self, response: str) -> str:
        r = response.lower()
        return "rag_query" if "【" in r and "source" in r else "outside_rag"

    # ------------------------
    # Core methods
    # ------------------------
    def create_user_message(self, user_query: str):
        log_step("create_user_message", f"Adding user message: {user_query}")
        self.project_client.agents.create_message(
            thread_id=self.thread.id,
            role="user",
            content=user_query
        )

    def process_agent_run(self):
        log_step("process_agent_run", "Starting agent run")
        run = self.project_client.agents.create_and_process_run(
            thread_id=self.thread.id,
            assistant_id=self.iam_agent.id
        )
        log_step("process_agent_run", "Agent run processed")
        return run

    def get_last_agent_response(self):
        log_step("get_last_agent_response", "Fetching last assistant message")
        messages = self.project_client.agents.list_messages(thread_id=self.thread.id)
        last_message = messages.get_last_text_message_by_role("assistant")
        return last_message.text.value if last_message and last_message.text else "No response received."

    def search_iam_docs_stream(self, user_query: str):
        """Generator yielding live observability steps and final response."""
        log_step("User query received", user_query)
        yield {"step": "User query received"}

        self.create_user_message(user_query)
        yield {"step": "User message added to thread"}

        run = self.process_agent_run()
        if run.status == "failed":
            error_msg = f"Run failed: {run.last_error}"
            log_step("Run failed", error_msg)
            yield {"operation": "Error", "response": error_msg}
            return
        yield {"step": "Agent run processed"}

        response = self.get_last_agent_response()
        yield {"step": "Assistant response retrieved"}

        # 🔍 Trace summary (only in trace_data, not in live logs)
        intent = self.infer_intent(user_query)
        system = self.infer_system(user_query)
        operation = self.detect_operation(response)
        agent = "IAMAssistant"
        attributes = None

        trace_data = {
            "intent": intent,
            "system": system,
            "agent": agent,
            "operation": operation,
            "attributes": attributes,
        }

        # Final structured response + trace data
        yield {"operation": "Response Ready", "response": response, "trace_data": trace_data}
