import os

from dotenv import load_dotenv

from semantic_kernel.functions import kernel_function

from azure.identity import DefaultAzureCredential
from azure.identity import ClientSecretCredential

from azure.ai.projects import AIProjectClient

from azure.ai.projects.models import AzureAISearchTool
 
load_dotenv()

credential=ClientSecretCredential(
    tenant_id=os.environ["TENANT_ID"],
    client_id=os.environ["CLIENT_ID_BACKEND"],
    client_secret=os.environ["CLIENT_SECRET_BACKEND"],
)

 
class IAMAssistant:

    def __init__(self, project_client: AIProjectClient):

        print("🔧 Initializing IAM Assistant...")

        self.project_client = project_client
        self.project_client = AIProjectClient.from_connection_string(
            # credential=DefaultAzureCredential(),
            credential=credential,
            conn_str=os.environ["AIPROJECT_CONNECTION_STRING"],
        )
 
        # Find Cognitive Search connection

        conn_list = self.project_client.connections.list()

        conn_id = next((conn.id for conn in conn_list if conn.connection_type == "CognitiveSearch"), None)

        if not conn_id:

            raise RuntimeError("❌ No Cognitive Search connection found for IAM documents.")
 
        # Configure Azure AI Search Tool

        self.ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="iam-docs-rag")
 
        # Create IAM agent

        self.iam_agent = self.project_client.agents.create_agent(

            model="gpt-4.1-nano",

            name="IAM Assistant",

            instructions="""
            You are an expert assistant focused exclusively on assisting users with tasks related to Identity and Access Management in Entra ID. 
You should ONLY use the provided IAM documentation for answering user queries from "tool_resources" (iam-docs-rag). When asked a query:
 
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
 
        # Create persistent thread

        self.thread = self.project_client.agents.create_thread()

        print("✅ IAM Assistant ready.\n")
 
    @kernel_function(description="Answer IAM-related questions using documentation.")

    async def answer_iam_question(self, question: str) -> str:

        """

        Handles IAM-related queries by invoking the agent with Azure AI Search context.

        """

        self.project_client.agents.create_message(

            thread_id=self.thread.id,

            role="user",

            content=question,

        )
 
        run = self.project_client.agents.create_and_process_run(

            thread_id=self.thread.id,

            assistant_id=self.iam_agent.id

        )
 
        if run.status == "failed":

            return f"❌ Run failed: {run.last_error}"
 
        messages = self.project_client.agents.list_messages(thread_id=self.thread.id)

        last_message = messages.get_last_text_message_by_role("assistant")
 
        return last_message.text.value if last_message and last_message.text else "🤖 No response received."
 