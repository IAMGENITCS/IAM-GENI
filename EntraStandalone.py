import asyncio
import os
import json
from dotenv import load_dotenv
from semantic_kernel.kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.contents.chat_history import ChatHistory
from provisioning_orch import ProvisioningAgent


load_dotenv()

# Azure AI Foundry connection
CHAT_MODEL          = os.environ["CHAT_MODEL"]
CHAT_MODEL_ENDPOINT = os.environ["CHAT_MODEL_ENDPOINT"]
CHAT_MODEL_API_KEY  = os.environ["CHAT_MODEL_API_KEY"]

DEBUG_MODE = True  # Toggle for verbose logging

def call_plugin(plugin_name, query, kernel):
    if DEBUG_MODE:
        print(f"\n🔌 [Plugin Invocation] Calling '{plugin_name}' with query:\n{query}\n")
    plugin = kernel.plugins[plugin_name]
    return plugin.invoke(query)

async def main():
    # 1) Initialize Kernel and AI service
    kernel = Kernel()
    service_id = "entra_provisioning"
    kernel.add_service(
        AzureChatCompletion(
            service_id=service_id,
            deployment_name=CHAT_MODEL,
            endpoint=CHAT_MODEL_ENDPOINT,
            api_key=CHAT_MODEL_API_KEY
        )
    )

    # 2) Register only ProvisioningAgent plugin
    kernel.add_plugin(
        ProvisioningAgent(),
        plugin_name="EntraProvisioning"
    )

    # 3) Configure orchestrator to pick the right function automatically
    settings = kernel.get_prompt_execution_settings_from_service_id(service_id)
    settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    # 4) Instructions only for Entra ID provisioning
    entraAgent = ChatCompletionAgent(
        service_id=service_id,
        kernel=kernel,
        name="EntraIDAgent",
        instructions="""
# Instruction Set for Entra ID Agent
 
You are an **Entra ID Provisioning Agent** for enterprise Identity and Access Management (IAM) that communicates with a user.
---
 
## Goal / Objective
 
* Identify the intent of the user:

* Do **not** use web search. Only work with available plugin.
**Do not guess or make unsupported inferences.** Only respond based on plugin capabilities or documented references.
 
---
 
## Plugin Descriptions
* **EntraProvisioning**:
 
  * Handles provisioning tasks in Entra ID.
  * Examples: listing users, creating users, managing groups in Entra ID, retrieving sign-in or audit logs related data.
 
---
 
## Use EntraProvisioning Plugin (Entra ID)
 
### User Tasks
 
* **Create a user** → Ask for `displayName`, `UPN`, `password`. Call the plugin only when all collected.
* **Get user details** → Ask for `UPN`. Call the plugin only when collected.
* **Update user profile** → Ask for `UPN`. Call the plugin only when collected.
* **Delete user profile** → Ask for `UPN` and **confirmation**. Call the plugin only when collected.
* **List users** → Ask for number of users to list. Call the plugin. Return response as per the collected number.
* **List users who have not signed in last 90 days-> Return the response as-is.
* **List users blocked by location-based Conditional Access policies in their sign-ins
* **List Entra ID administrators who have not registered Certificate-based authentication.
 
### Group Tasks
 
* **Create group** → Ask for `displayName`, `mailNickname`. Call the plugin only when collected.
* **Add user to group** → Ask for `userId` and `groupId`. Call the plugin only when collected.
* **Remove user from group** → Ask for `userId`, `groupId`, and **confirmation**. Call the plugin only when confirmed.
* **Assign owner to group** → Ask for `ownerId` and `groupId`. Call the plugin only when collected.
* **Delete group** → Ask for `groupId` and **confirmation**. Call the plugin only when confirmed.
* **Get group details** → Ask for `groupId`. Call the plugin only when collected.
* **List groups** → Ask for number of groups to list. Call the plugin only when collected. Return response as-is.
* **Show group owners** → Ask for `groupId`. Call the plugin only when collected.
* **Show group members** → Ask for `groupId`. Call the plugin only when collected.
* **Count ownerless groups** → Call directly. Return response as-is.
* **Update group details** → Ask for `groupId` and details to update. Call the plugin only when collected.
* **List/show ownerless groups** → Ask for number to list. Call the plugin only when collected. Return response as-is.
* **List groups whose owners are inactive -> Ask for number to list. Call the plugin only when collected. Return response as-is

---
 
## Response Rules
 
* Always ask the user clearly for any missing required inputs before calling a plugin.
* Only call plugins once all required inputs are collected.
* Return plugin responses **exactly as received**, without modification.
 
⚠️ Always return in **valid JSON** for provisioning tasks for Entra ID, e.g.:
 
```json
{
  "action": "provision",
  "result": "<plugin response>"
}
```
""",
        execution_settings=settings
    )

    # 5) Conversation state
    chat_history = ChatHistory()
    print("=== 🛡️ Entra ID Provisioning Agent Ready ===")

    while True:
        user_input = input("\n> ").strip()
        if not user_input or user_input.lower() in ("exit", "quit"):
            print("👋 Goodbye.")
            break

        chat_history.messages.append(
            ChatMessageContent(role=AuthorRole.USER, content=user_input)
        )

        async for response in entraAgent.invoke(chat_history):
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

            if action == "provision":
                print(f"\n✅ [Entra Pro Invoked]\n{result}")
            else:
                # print(f"\n⚠️ [Unknown Action] Orchestrator may have replied directly:\n{response.content}")
                print(f"\n [Orchestrator Response] :\n{response.content}")

            chat_history.messages.append(
                ChatMessageContent(role=AuthorRole.ASSISTANT, content=response.content)
            )

if __name__ == "__main__":
    asyncio.run(main())