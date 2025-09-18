import requests
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("CHAT_MODEL_API_KEY"),
    api_version="2023-07-01-preview",
    azure_endpoint=os.getenv("CHAT_MODEL_ENDPOINT")
)

INTENT_SYSTEM_PROMPT = """
You are an IAM provisioning assistant. Your job is to classify user requests into one of the following intents:

User operations:
- list_users
- list_top_users
- get_user_details
- create_user
- update_user
- delete_user

Group operations:
- list_groups
- get_group_details
- create_group
- update_group
- delete_group
- add_user_to_group
- remove_user_from_group
- assign_owner_to_group

Respond with a JSON object like:
{
  "intent": "create_group"
}
Only return the JSON. Do not explain or add commentary.
"""

def detect_intent(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    content = response.choices[0].message.content
    try:
        return eval(content)["intent"]
    except Exception:
        return "unknown"


# ProvisioningAgent class to handle IAM operations

class ProvisioningAgent:
    def __init__(self):
        self.credential = DefaultAzureCredential()
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        self.token = self.get_access_token()
        print("🔐 Access token acquired.")

    def get_access_token(self) -> str:
        token = self.credential.get_token("https://graph.microsoft.com/.default")
        return token.token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def list_users(self):
        url = f"{self.graph_base_url}/users"
        response = requests.get(url, headers=self._headers())
        if response.status_code == 200:
            users = response.json().get("value", [])
            return [f"- {u['displayName']} ({u['userPrincipalName']})" for u in users]
        else:
            return [f"❌ Error: {response.status_code} - {response.text}"]

    def list_top_users(self, count=10):
        url = f"{self.graph_base_url}/users?$top={count}"
        response = requests.get(url, headers=self._headers())
        if response.status_code == 200:
            users = response.json().get("value", [])
            return [f"- {u['displayName']} ({u['userPrincipalName']})" for u in users]
        else:
            return [f"❌ Error: {response.status_code} - {response.text}"]

    def get_user_details(self, user_id):
        url = f"{self.graph_base_url}/users/{user_id}"
        response = requests.get(url, headers=self._headers())
        if response.status_code == 200:
            user = response.json()
            return [
                f"👤 Display Name: {user.get('displayName')}",
                f"📧 Email: {user.get('userPrincipalName')}",
                f"🏢 Department: {user.get('department', 'N/A')}",
                f"🧑‍💼 Job Title: {user.get('jobTitle', 'N/A')}"
            ]
        else:
            return [f"❌ Error: {response.status_code} - {response.text}"]

    def create_user(self, display_name, user_principal_name, password):
        url = f"{self.graph_base_url}/users"
        payload = {
            "accountEnabled": True,
            "displayName": display_name,
            "mailNickname": user_principal_name.split("@")[0],
            "userPrincipalName": user_principal_name,
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": password
            }
        }
        response = requests.post(url, headers=self._headers(), json=payload)
        if response.status_code == 201:
            return f"✅ User '{display_name}' created successfully."
        else:
            return f"❌ Error: {response.status_code} - {response.text}"

    def update_user(self, user_id, field, value):
        url = f"{self.graph_base_url}/users/{user_id}"
        payload = {field: value}
        response = requests.patch(url, headers=self._headers(), json=payload)
        if response.status_code == 204:
            return f"✅ User '{user_id}' updated: {field} → {value}"
        else:
            return f"❌ Error: {response.status_code} - {response.text}"

    def delete_user(self, user_id):
        url = f"{self.graph_base_url}/users/{user_id}"
        response = requests.delete(url, headers=self._headers())
        if response.status_code == 204:
            return f"🗑️ User '{user_id}' deleted successfully."
        else:
            return f"❌ Error: {response.status_code} - {response.text}"
        

    #-------------------------- Group Management --------------------------#

    def list_groups(self):
        url = f"{self.graph_base_url}/groups"   
        headers = self._headers()
        response = requests.get(url, headers=headers)   
        if response.status_code == 200:
            groups = response.json().get("value", [])
            return [f"- {group['displayName']} ({group['mailNickname']})" for group in groups]
        else:
            return [f"❌ Error fetching groups: {response.status_code} - {response.text}"]



    def create_group(self, display_name: str, mail_nickname: str, is_security_enabled: bool = True):
        url = f"{self.graph_base_url}/groups"
        headers = self._headers()
        payload = {
            "displayName": display_name,
            "mailEnabled": False,
            "mailNickname": mail_nickname,
            "securityEnabled": True,
            "groupTypes": [] if is_security_enabled else ["Unified"]

        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            return f"✅ Group '{display_name}' created successfully."
        else:
            return f"❌ Error creating group: {response.status_code} - {response.text}"
        
    def Add_user_to_group(self, user_id: str, group_id: str):
        url = f"{self.graph_base_url}/groups/{group_id}/members/$ref"
        headers = self._headers()
        payload = {
            "@odata.id": f"{self.graph_base_url}/users/{user_id}"
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 204:
            return f"✅ User '{user_id}' added to group '{group_id}' successfully."
        else:
            return f"❌ Error adding user to group: {response.status_code} - {response.text}"
        
    def remove_user_from_group(self, user_id: str, group_id: str):
        url = f"{self.graph_base_url}/groups/{group_id}/members/{user_id}/$ref"
        headers = self._headers()
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            return f"✅ User '{user_id}' removed from group '{group_id}' successfully."
        else:
            return f"❌ Error removing user from group: {response.status_code} - {response.text}"
        
    def group_details(self, group_id: str):
        url = f"{self.graph_base_url}/groups/{group_id}"
        headers = self._headers()
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            group = response.json()
            return [
                f"👥 Group Name: {group.get('displayName')}",
                f"📧 Mail Nickname: {group.get('mailNickname')}",
                f"🔒 Security Enabled: {group.get('securityEnabled')}",
                f"📅 Created Date: {group.get('createdDateTime')}"
            ]
        else:
            return [f"❌ Error fetching group details: {response.status_code} - {response.text}"]
        
    def assign_owner(self, group_id: str, owner_id: str):
        url = f"{self.graph_base_url}/groups/{group_id}/owners/$ref"
        headers = self._headers()
        payload = {
            "@odata.id": f"{self.graph_base_url}/users/{owner_id}"
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 204:
            return f"✅ Owner '{owner_id}' assigned to group '{group_id}' successfully."
        else:
            return f"❌ Error assigning owner: {response.status_code} - {response.text}"
        
    def delete_group(self, group_id: str):
        url = f"{self.graph_base_url}/groups/{group_id}"
        headers = self._headers()
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            return f"🗑️ Group '{group_id}' deleted successfully."
        else:
            return f"❌ Error deleting group: {response.status_code} - {response.text}"


    def chat(self):
        print("💬 ProvisioningAgent ready. Type 'exit' to quit.\n")
        while True:
            user_input = input("You: ")
            if user_input.lower() == "exit":
                break

            intent = detect_intent(user_input)

            if intent == "list_users":
                users = self.list_users()
                print("\n👥 Users in Entra ID:")
                for u in users:
                    print(u)

            elif intent == "list_top_users":
                count = input("How many users would you like to list? (default 10): ")
                try:
                    count = int(count)
                except ValueError:
                    count = 10
                users = self.list_top_users(count)
                print(f"\n👥 Top {count} Users:")
                for u in users:
                    print(u)

            elif intent == "get_user_details":
                user_id = input("Enter userPrincipalName or object ID: ")
                details = self.get_user_details(user_id)
                print("\n📄 User Details:")
                for line in details:
                    print(line)

            elif intent == "create_user":
                print("🆕 Let's create a new user.")
                name = input("Enter display name: ")
                email = input("Enter userPrincipalName (e.g., user@domain.com): ")
                password = input("Enter temporary password: ")
                result = self.create_user(name, email, password)
                print(result)

            elif intent == "update_user":
                user_id = input("Enter userPrincipalName or object ID: ")
                field = input("Which field to update? (e.g., jobTitle): ")
                value = input(f"New value for {field}: ")
                result = self.update_user(user_id, field, value)
                print(result)

            elif intent == "delete_user":
                user_id = input("Enter userPrincipalName or object ID: ")
                confirm = input(f"Are you sure you want to delete '{user_id}'? (yes/no): ")
                if confirm.lower() == "yes":
                    result = self.delete_user(user_id)
                    print(result)
                else:
                    print("❌ Deletion cancelled.")

            elif intent == "create_group":
                print("🆕 Let's create a new group.")
                display_name = input("Enter group display name: ")
                mail_nickname = input("Enter group mail nickname: ")
                is_security_enabled = input("Is this a security group? (yes/no): ").strip().lower() == "yes"
                result = self.create_group(display_name, mail_nickname, is_security_enabled)
                print(result)

            elif intent == "list_groups":
                groups = self.list_groups()
                print("\n👥 Groups in Entra ID:")
                for g in groups:
                    print(g)
            
            elif intent == "add_user_to_group":
                user_id = input("Enter user ID to add: ")
                group_id = input("Enter group ID to add the user to: ")
                result = self.Add_user_to_group(user_id, group_id)
                print(result)   

            elif intent == "remove_user_from_group":
                user_id = input("Enter user ID to remove: ")
                group_id = input("Enter group ID to remove the user from: ")
                result = self.remove_user_from_group(user_id, group_id)
                print(result)

            elif intent == "group_details":
                group_id = input("Enter group ID to get details: ")
                details = self.group_details(group_id)
                print("\n📄 Group Details:")
                for line in details:
                    print(line)
            
            elif intent == "assign_owner":
                group_id = input("Enter group ID to assign owner: ")
                owner_id = input("Enter owner user ID to assign: ")
                result = self.assign_owner(group_id, owner_id)
                print(result)

            elif intent == "delete_group":
                group_id = input("Enter group ID to delete: ")
                confirm = input(f"Are you sure you want to delete group '{group_id}'? (yes/no): ")
                if confirm.lower() == "yes":
                    result = self.delete_group(group_id)
                    print(result)
                else:
                    print("❌ Deletion cancelled.")


            else:
                print("🤖 I didn't quite catch that. Try rephrasing your request.")

if __name__ == "__main__":
    agent = ProvisioningAgent()
    agent.chat()