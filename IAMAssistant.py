import os
import logging
import json
from semantic_kernel.functions import kernel_function
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ConnectionType
from azure.identity import DefaultAzureCredential
from azure.identity import ClientSecretCredential
from azure.ai.projects.models import AzureAISearchTool
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown


load_dotenv()

# logging.basicConfig(level=logging.DEBUG)
credential=ClientSecretCredential(
    tenant_id=os.environ["TENANT_ID"],
    client_id=os.environ["CLIENT_ID_BACKEND"],
    client_secret=os.environ["CLIENT_SECRET_BACKEND"],
)

class IAMAssistant:
    """
    A class to represent the IAM Assistant with persistent thread and agent for multi-turn conversations.
    """
 
    def __init__(self):
        print("🔧 Initializing IAM Assistant...")
 
        # Connect to Azure AI Project
        self.project_client = AIProjectClient.from_connection_string(
            # credential=DefaultAzureCredential(),
            credential=credential,
            conn_str=os.environ["AIPROJECT_CONNECTION_STRING"],
        )
 
        # Identify Cognitive Search connection
        conn_list = self.project_client.connections.list()
        conn_id = next((conn.id for conn in conn_list if conn.connection_type == "CognitiveSearch"), None)
 
        if not conn_id:
            raise RuntimeError("No Cognitive Search connection found for IAM documents.")
 
        # Configure Azure AI Search Tool
        self.ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="end-user-rag")

        # Create agent once for the session
        self.iam_agent = self.project_client.agents.create_agent(
            model="gpt-4.1-nano",
            name="iam Assistant",
            instructions="""
            You are an expert assistant focused exclusively on assisting users with tasks related to Identity and Access Management in Entra ID. 
# You should ONLY use the provided IAM documentation for answering user queries from "tool_resources" (end-user-rag). When asked a query:
 
1. **Search the documentation**: Use the "ai search tool" to retrieve relevant content from the IAM documentation for the user query.
2. **No external sources**: Do not use the web or any external sources to generate answers.
3. **Refuse unsupported queries**: If you cannot find relevant information in the documentation, say: "I don't know the answer to that. My responses are based solely on the IAM documentation."
4. **Provide clear and concise responses**: If the documentation contains information, respond with the most relevant content. If not, say: "The information is not available in the documentation."
5. **Do not guess or make inferences**: Only answer based on whats available in the documentation.
 
Always ensure the responses are professional and accurate.
            """,
            tools=self.ai_search.definitions,
            tool_resources=self.ai_search.resources,
        )
 
        # Create a persistent thread
        self.thread = self.project_client.agents.create_thread()
        print("✅ Agent and thread ready for conversation.\n")
 
    def chat(self):
        """
        Starts a terminal-based chat loop with the IAM agent.
        """
        print("💬 Start chatting with IAM Assistant. Type 'exit' to end.\n")
        while True:
            user_query = input("You: ")
            if user_query.lower() == "exit":
                break
 
            response = self.search_iam_docs(user_query)
            # print(f"Agent: {response}\n")
            console = Console()
            console.print(Panel.fit(Markdown(response), title="IAM Assistant", border_style="cyan"))

 
    def search_iam_docs(self, user_query: str) -> str:
        """
        Adds a user message to the thread and retrieves the agent's response.
        """
        self.project_client.agents.create_message(
            thread_id=self.thread.id,
            role="user",
            content=f"{user_query}",
        )
 
        run = self.project_client.agents.create_and_process_run(
            thread_id=self.thread.id,
            assistant_id=self.iam_agent.id
        )
 
        if run.status == "failed":
            return f"Run failed:\nCode: {run.last_error.get('code')}\nMessage: {run.last_error.get('message')}"


        # if run.status == "failed":
        #     return f"Run failed: {run.last_error}"
 
        messages = self.project_client.agents.list_messages(thread_id=self.thread.id)
        last_message= messages.get_last_text_message_by_role("assistant")

        return last_message.text.value if last_message and last_message.text else "No response received."
 
 
if __name__ == "__main__":
    agent = IAMAssistant()
    agent.chat()