import os
import logging
import json
from semantic_kernel.functions import kernel_function
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ConnectionType
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import AzureAISearchTool
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from azure.identity import ClientSecretCredential

 
load_dotenv()
credential=ClientSecretCredential(
    tenant_id=os.environ["TENANT_ID"],
    client_id=os.environ["CLIENT_ID_BACKEND"],
    client_secret=os.environ["CLIENT_SECRET_BACKEND"]
)
class IAMAssistant:
    """
    IAM Assistant with explicit thread control.
    - Initialize once (agent + tools)
    - Create threads per user/session
    - Send messages on a given thread
    """
    def __init__(self):
        # Initialize Azure AI Project and Search tool once
        self.project_client = AIProjectClient.from_connection_string(
            # credential=DefaultAzureCredential(),
            credential=credential,
            conn_str=os.environ["AIPROJECT_CONNECTION_STRING"],
        )

        # Find Cognitive Search connection
        conn_list = self.project_client.connections.list()
        conn_id = next(
            (conn.id for conn in conn_list if conn.connection_type == "CognitiveSearch"),
            None
        )
        if not conn_id:
            raise RuntimeError("No Cognitive Search connection found for IAM documents.")

        # Configure Azure AI Search Tooll
        self.ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="iam-docs-rag")

        # Create the agent once
        self.iam_agent = self.project_client.agents.create_agent(
            model="gpt-4.1-nano",  # ensure this model exists in your Azure project
            name="IAM Assistant",
            instructions=
                """You are an expert assistant focused exclusively on assisting users with tasks related to Identity and Access Management in Entra ID. 
You should ONLY use the provided IAM documentation for answering user queries from "tool_resources" (iam-docs-rag). When asked a query:
1. **Search the documentation**: Use the "ai search tool" to retrieve relevant content from the IAM documentation for the user query.
2. **No external sources**: Do not use the web or any external sources to generate answers.
3. **Refuse unsupported queries**: If you cannot find relevant information in the documentation, say: "I don't know the answer to that. My responses are based solely on the IAM documentation."
4. **Provide clear and concise responses**: If the documentation contains information, respond with the most relevant content. If not, say: "The information is not available in the documentation."
5. **Do not guess or make inferences**: Only answer based on what’s available in the documentation.
Always ensure the responses are professional and accurate."""
            ,
            tools=self.ai_search.definitions,
            tool_resources=self.ai_search.resources,
        )

    def create_thread(self) -> str:
        """Create and return a new thread id."""
        thread = self.project_client.agents.create_thread()
        return thread.id

    def chat_on_thread(self, thread_id: str, user_query: str) -> str:
        """Send a user message to a given thread and return the assistant response text."""
        self.project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=user_query,
        )
        run = self.project_client.agents.create_and_process_run(
            thread_id=thread_id,
            assistant_id=self.iam_agent.id
        )
        if run.status == "failed":
            return f"Run failed: {run.last_error}"

        messages = self.project_client.agents.list_messages(thread_id=thread_id)
        last_message = messages.get_last_text_message_by_role("assistant")
        return last_message.text.value if last_message and last_message.text else "No response received."

# You call this when a new user session starts (Streamlit’s first request).

# Azure returns a thread.id. Keep it and reuse it for all messages in that chat.
















# # follow-up ques integrations

# class IAMAssistant:
#     """
#     IAM Assistant with explicit thread control.
#     - Initialize once (agent + tools)
#     - Create threads per user/session
#     - Send messages on a given thread
#     """
    
#     def __init__(self):
#         # Initialize Azure AI Project and Search tool once
#         self.project_client = AIProjectClient.from_connection_string(
#             credential=DefaultAzureCredential(),
#             conn_str=os.environ["AIPROJECT_CONNECTION_STRING"],
#         )

#         # Find Cognitive Search connection
#         conn_list = self.project_client.connections.list()
#         conn_id = next(
#             (conn.id for conn in conn_list if conn.connection_type == "CognitiveSearch"),
#             None
#         )
#         if not conn_id:
#             raise RuntimeError("No Cognitive Search connection found for IAM documents.")

#         # Configure Azure AI Search Tooll
#         self.ai_search = AzureAISearchTool(index_connection_id=conn_id, index_name="iam-docs-rag")

#         # Create the agent once
#         self.iam_agent = self.project_client.agents.create_agent(
#             model="gpt-4.1-nano",  # ensure this model exists in your Azure project
#             name="IAM Assistant",
#             instructions= 
#             """
# You are an expert assistant focused exclusively on assisting users with tasks related to Identity and Access Management in Entra ID. 
# You should ONLY use the provided IAM documentation for answering user queries from "tool_resources" (iam-docs-rag). When asked a query:
# 1. **Search the documentation**: Use the "ai search tool" to retrieve relevant content from the IAM documentation for the user query.
# 2. **No external sources**: Do not use the web or any external sources to generate answers.
# 3. **Refuse unsupported queries**: If you cannot find relevant information in the documentation, say: "I don't know the answer to that. My responses are based solely on the IAM documentation."
# 4. **Provide clear and concise responses**: If the documentation contains information, respond with the most relevant content. If not, say: "The information is not available in the documentation."
# 5. **Ask follow-up questions**: If the response to the query suggests that further clarification or action is needed, ask a relevant follow-up question and store it.
# 6. **Store follow-up questions**: Store any follow-up questions generated in a variable called `follow_up_questions`. The variable will store the list of follow-up questions for each thread.
# 7. **Do not guess or make inferences**: Only answer based on what’s available in the documentation.
# Always ensure the responses are professional and accurate.
#             """
#             ,  # Updated instructions including follow-up logic
#             tools=self.ai_search.definitions,
#             tool_resources=self.ai_search.resources,
#         )
        
#         # Variable to store follow-up questions per thread
#         self.follow_up_questions = {}

#     def create_thread(self) -> str:
#         """Create and return a new thread id."""
#         thread = self.project_client.agents.create_thread()
#         self.follow_up_questions[thread.id] = []  # Initialize empty list for follow-ups
#         return thread.id

#     def chat_on_thread(self, thread_id: str, user_query: str) -> str:
#         """Send a user message to a given thread and return the assistant response text."""
        
#         # Step 1: Send the user's query to the thread
#         self.project_client.agents.create_message(
#             thread_id=thread_id,
#             role="user",
#             content=user_query,
#         )
        
#         # Step 2: Process the query and get the assistant's response
#         run = self.project_client.agents.create_and_process_run(
#             thread_id=thread_id,
#             assistant_id=self.iam_agent.id
#         )
        
#         if run.status == "failed":
#             return f"Run failed: {run.last_error}"

#         # Step 3: Retrieve messages from the thread
#         messages = self.project_client.agents.list_messages(thread_id=thread_id)
#         last_message = messages.get_last_text_message_by_role("assistant")

#         # Step 4: If a follow-up question is detected, store it
#         follow_up_question = None
#         if last_message and last_message.text:
#             response_text = last_message.text.value
#             if "follow-up" in response_text.lower():  # Example: checking if follow-up is needed
#                 follow_up_question = "Can you clarify that further?"
#                 self.follow_up_questions[thread_id].append(follow_up_question)

#         follow_up_question = None
#         if last_message and last_message.text:
    #         response_text = last_message.text.value
    #         if "follow-up" in response_text.lower():  # Example: checking if follow-up is needed
    #             follow_up_question = "Can you clarify that further?"
    #             self.follow_up_questions[thread_id].append(follow_up_question)
        
    #     # Step 5: Return the main response to the user without the follow-up question
    #     return last_message.text.value if last_message and last_message.text else "No response received."
            

    # def get_follow_up_questions(self, thread_id: str):
    #     """Fetch stored follow-up questions for a thread."""
    #     return self.follow_up_questions.get(thread_id, [])
