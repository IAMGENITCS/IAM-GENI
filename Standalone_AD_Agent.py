import os
import json
import logging
#logging.basicConfig(level=logging.DEBUG)
from dotenv import load_dotenv
from semantic_kernel.kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from semantic_kernel.contents.chat_history import ChatHistory

# Plugin classes
from AD_provisioning_Agent import AD_Provisioning_Agent

load_dotenv()

# Azure AI Foundry connection
AIPROJECT_CONN_STR      = os.environ["AIPROJECT_CONNECTION_STRING"]
CHAT_MODEL              = os.environ["CHAT_MODEL"]
CHAT_MODEL_ENDPOINT     = os.environ["CHAT_MODEL_ENDPOINT"]
CHAT_MODEL_API_KEY      = os.environ["CHAT_MODEL_API_KEY"]

DEBUG_MODE = True  # Toggle for verbose logging

def call_plugin(plugin_name, query, kernel):
    if DEBUG_MODE:
        print(f"\n🔌 [Plugin Invocation] Calling '{plugin_name}' with query:\n{query}\n")
    plugin = kernel.plugins[plugin_name]
    return plugin.invoke(query)

async def main():
    # 1) Initialize Kernel and AI service
    kernel = Kernel()
    service_id = "AD_Provisioning_Agent_Service"
    kernel.add_service(
        AzureChatCompletion(
            service_id=service_id,
            deployment_name=CHAT_MODEL,
            endpoint=CHAT_MODEL_ENDPOINT,
            api_key=CHAT_MODEL_API_KEY
        )
    )

    #AD_Provisioning_Agent
    kernel.add_plugin(
        AD_Provisioning_Agent(),
        plugin_name="AD_Provisioning_Agent"
    )

  

    # 3) Configure orchestrator to pick the right function
    settings = kernel.get_prompt_execution_settings_from_service_id(service_id)
    settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    # 4) Orchestrator instructions
    orchestrator = ChatCompletionAgent(
        service_id=service_id,
        kernel=kernel,
        name="AD_Provisioning_Agent",
        instructions="""
# Instruction Set for AD Provisioning Agent

You are an AD Provisioning Agent that communicates with an Admin user and performs operations in Active Directory (AD) by invoking functions from the AD_Plugin. Do not use web search.

Goal:
- Detect the user intent and call the correct AD_Plugin function with the required parameters.
- When the user intent is to get totals first (e.g., list users/groups/ownerless groups), first call the appropriate function with count=0 (and list_all=False) to get the total and prompt for how many to list.

Available plugin: AD_Plugin
- Functions and expected usage patterns:
  - list_users(count=0, list_all=False)
    - If intent is "list users": call with count=0 to get totals first. If user says "list N" then call with count=N. If "list all" then call with list_all=True.
  - list_inactive_users(count=0, list_all=False)
    - If intent is about inactive/disabled users: same pattern as list_users.
  - get_user_details(common_name)
  - create_user(common_name, user_principal_name, password)
  - update_user(common_name, field, value)
  - delete_user(common_name)
  - ListGroups → list_groups(count=0, list_all=False) [Semantic Kernel function name is list_groups, exported as ListGroups]
  - get_group_details(common_name)
  - create_group(common_name, description)
  - show_group_owner(common_name)
  - show_group_members(common_name, count=0, list_all=False)
    - First return total and ask how many to show unless user asks for all or gives a number.
  - assign_group_owner(group_cn, owner_cn)
  - add_user_to_group(user_cn, group_cn)
  - remove_user_from_group(user_cn, group_cn)
  - delete_group(common_name)
  - groups_without_owner(action="list|count|both", count=0)
    - If intent is to know totals first: call with action="both", count=0. If user asks to list N, call with action="list", count=N.
  - update_group_details(group_cn, new_cn=None, description=None, owner_cn=None)
  - get_group_info(group_cn)
  - list_inactive_owner_groups(limit=5, count_only=False)
    - If user asks for count only: call with count_only=True. If user asks to list N: call with limit=N.
  - groups_not_following_naming_convention(allowed_prefixes=[...], count=0)
    - Ask for allowed_prefixes if not provided. First call with count=0 to get total, then ask how many to list.
  - groups with_zero_members(count=0)
    - If intent is to know totals first: call with count=0. If user asks to list N, call with count=N.  
    
Response rules:
- Ask for missing parameters clearly when needed (e.g., CNs, counts, prefixes, confirmation for destructive actions).
- Never fabricate counts or lists. Always call an AD_Plugin function to obtain totals/lists.
- Return ONLY a JSON object with this envelope and put the RAW plugin response string into result without modification or extra commentary:
{
  "action": "ad_provision",
  "agent": "<AD_Provisioning_Agent>",
  "result": "<raw JSON or string returned by the AD_Plugin function>"
}

Examples:
- User: "list users"
  -> Call AD_Plugin.list_users(count=0, list_all=False) and return the raw JSON in result.
- User: "list ownerless groups"
  -> Call AD_Plugin.groups_without_owner(action="both", count=0) and return the raw JSON in result.
        """,
        execution_settings=settings
    )


    chat_history = ChatHistory()
    print("=== 🛡️ AD Provisioning Agent  ===")

    while True:
        user_input = input("\n> ").strip()
        if not user_input or user_input.lower() in ("exit", "quit"):
            print("👋 Goodbye.")
            break
      

        chat_history.messages.append(
            ChatMessageContent(role=AuthorRole.USER, content=user_input)
        )

        async for response in orchestrator.invoke(chat_history):
            # if DEBUG_MODE:
            #     print(f"\n🧠 [Raw Orchestrator Response]\n{response.content}\n")

            try:
                payload = json.loads(response.content)
            except json.JSONDecodeError:
                #print("❌ Orchestrator returned non-JSON. Possible direct response or malformed output.")
                #print("Response is not in JSON format. Orchestrator may have replied directly.")
                print(response.content)
                continue

            action = payload.get("action")
            result = payload.get("result")
            
            if action == "ad_provision":
                print(f"\n✅ [AD Pro Invoked]\n{result}")
            else:
                # print(f"\n⚠️ [Unknown Action] Orchestrator may have replied directly:\n{response.content}")
                print(f"\n [Orchestrator Response] :\n{response.content}")

              
            chat_history.messages.append(
                ChatMessageContent(role=AuthorRole.ASSISTANT, content=response.content)
            )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
