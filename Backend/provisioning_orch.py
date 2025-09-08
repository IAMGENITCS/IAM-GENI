import os
import requests
from dotenv import load_dotenv
from semantic_kernel.functions import kernel_function
from azure.identity import DefaultAzureCredential
 
load_dotenv()
 
class ProvisioningAgent:
    def __init__(self):
        print("🔧 Initializing Provisioning Agent...")
        # Acquire token for Graph
        self.credential = DefaultAzureCredential()
        token = self.credential.get_token("https://graph.microsoft.com/.default")
        self._headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        print("✅ Provisioning Agent ready.\n")
 
    @kernel_function(description="List all users in Entra ID.")
    async def list_users(self) -> str:
        url = f"{self.graph_base_url}/users"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return f"❌ Error listing users: {resp.status_code} – {resp.text}"
        users = resp.json().get("value", [])
        if not users:
            return "ℹ️ No users found."
        lines = [f"- {u['displayName']} ({u['userPrincipalName']})" for u in users]
        return "\n".join(lines)
 
    @kernel_function(description="Get details for a specific user by UPN or object ID.")
    async def get_user_details(self, user_id: str) -> str:
        url = f"{self.graph_base_url}/users/{user_id}"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return f"❌ Error fetching user '{user_id}': {resp.status_code} – {resp.text}"
        u = resp.json()
        details = [
            f"👤 Display Name: {u.get('displayName')}",
            f"📧 UPN: {u.get('userPrincipalName')}",
            f"🏢 Department: {u.get('department','N/A')}",
            f"🧑‍💼 Title: {u.get('jobTitle','N/A')}"
        ]
        return "\n".join(details)
 
    @kernel_function(description="Create a new user in Entra ID.")
    async def create_user(self,
                          display_name: str="",
                          user_principal_name: str="",
                          password: str="") -> str:
        
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
        resp = requests.post(url, headers=self._headers, json=payload)
        if resp.status_code == 201:
            return f"✅ User '{display_name}' created."
        return f"❌ Error creating user: {resp.status_code} – {resp.text}"
 
    @kernel_function(description="Update a field for an existing user.")
    async def update_user(self,
                          user_id: str,
                          field: str,
                          value: str) -> str:
        url = f"{self.graph_base_url}/users/{user_id}"
        payload = {field: value}
        resp = requests.patch(url, headers=self._headers, json=payload)
        if resp.status_code == 204:
            return f"✅ Updated user '{user_id}': set {field} = {value}"
        return f"❌ Error updating user: {resp.status_code} – {resp.text}"
 
    @kernel_function(description="Delete a user from Entra ID.")
    async def delete_user(self, user_id: str) -> str:
        url = f"{self.graph_base_url}/users/{user_id}"
        resp = requests.delete(url, headers=self._headers)
        if resp.status_code == 204:
            return f"🗑️ User '{user_id}' deleted."
        return f"❌ Error deleting user: {resp.status_code} – {resp.text}"
 
    # --------------------- Group Operations --------------------- #
 
    @kernel_function(description="List a number of groups in Entra ID.")
    # async def list_groups(self) -> str:
    #     url = f"{self.graph_base_url}/groups"
    #     resp = requests.get(url, headers=self._headers)
    #     if resp.status_code != 200:
    #         return f"❌ Error listing groups: {resp.status_code} – {resp.text}"
    #     groups = resp.json().get("value", [])
    #     if not groups:
    #         return "ℹ️ No groups found."
    #     lines = [f"- {g['displayName']} ({g['mailNickname']})" for g in groups]
    #     return "\n".join(lines)
    async def list_groups(self, max_results: int) -> str:

        # Enforce a sane upper bound (Graph allows up to 999 per page)

        page_size = min(max_results, 999)

        url = f"{self.graph_base_url}/groups?$top={page_size}"

        headers = self._headers.copy()
 
        all_groups = []

        while url and len(all_groups) < max_results:

            resp = requests.get(url, headers=headers)

            if resp.status_code != 200:

                return f"❌ Error listing groups: {resp.status_code} – {resp.text}"
 
            payload = resp.json()

            batch = payload.get("value", [])

            all_groups.extend(batch)
 
            # Graph next-page link, if more remain

            url = payload.get("@odata.nextLink", None)
 
            # If we already hit our limit, break out

            if len(all_groups) >= max_results:

                break
 
        # Trim to exactly max_results

        groups = all_groups[:max_results]

        if not groups:

            return "ℹ️ No groups found."
 
        lines = [f"- {g['displayName']} ({g.get('mailNickname','')})" for g in groups]

        return "\n".join(lines)
 
 
    @kernel_function(description="Get details for a specific group by its object ID.")
    async def get_group_details(self, group_id: str) -> str:
        url = f"{self.graph_base_url}/groups/{group_id}"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return f"❌ Error fetching group '{group_id}': {resp.status_code} – {resp.text}"
        g = resp.json()
        details = [
            f"👥 Name: {g.get('displayName')}",
            f"📧 Nickname: {g.get('mailNickname')}",
            f"🔒 Security Enabled: {g.get('securityEnabled')}",
            f"📅 Created: {g.get('createdDateTime')}"
        ]
        return "\n".join(details)
 
    @kernel_function(description="Create a new security-enabled group in Entra ID.")
    async def create_group(self,
                           display_name: str,
                           mail_nickname: str) -> str:
        url = f"{self.graph_base_url}/groups"
        payload = {
            "displayName": display_name,
            "mailEnabled": False,
            "mailNickname": mail_nickname,
            "securityEnabled": True,
            "groupTypes": []
        }
        resp = requests.post(url, headers=self._headers, json=payload)
        if resp.status_code == 201:
            return f"✅ Group '{display_name}' created."
        return f"❌ Error creating group: {resp.status_code} – {resp.text}"
 
    @kernel_function(description="Delete an existing group in Entra ID.")
    async def delete_group(self, group_id: str) -> str:
        url = f"{self.graph_base_url}/groups/{group_id}"
        resp = requests.delete(url, headers=self._headers)
        if resp.status_code == 204:
            return f"🗑️ Group '{group_id}' deleted."
        return f"❌ Error deleting group: {resp.status_code} – {resp.text}"
 
    @kernel_function(description="Add a user to a group in Entra ID.")
    async def add_user_to_group(self,
                                user_id: str,
                                group_id: str) -> str:
        url = f"{self.graph_base_url}/groups/{group_id}/members/$ref"
        payload = {"@odata.id": f"{self.graph_base_url}/users/{user_id}"}
        resp = requests.post(url, headers=self._headers, json=payload)
        if resp.status_code == 204:
            return f"✅ User '{user_id}' added to group '{group_id}'."
        return f"❌ Error adding user to group: {resp.status_code} – {resp.text}"
 
    @kernel_function(description="Remove a user from a group in Entra ID.")
    async def remove_user_from_group(self,
                                     user_id: str,
                                     group_id: str) -> str:
        url = f"{self.graph_base_url}/groups/{group_id}/members/{user_id}/$ref"
        resp = requests.delete(url, headers=self._headers)
        if resp.status_code == 204:
            return f"🚪 User '{user_id}' removed from group '{group_id}'."
        return f"❌ Error removing user from group: {resp.status_code} – {resp.text}"
 
    @kernel_function(description="Assign an owner to a group in Entra ID.")
    async def assign_owner_to_group(self,
                                    owner_id: str,
                                    group_id: str) -> str:
        url = f"{self.graph_base_url}/groups/{group_id}/owners/$ref"
        payload = {"@odata.id": f"{self.graph_base_url}/users/{owner_id}"}
        resp = requests.post(url, headers=self._headers, json=payload)
        if resp.status_code == 204:
            return f"👑 User '{owner_id}' assigned as owner of group '{group_id}'."
        return f"❌ Error assigning owner: {resp.status_code} – {resp.text}"
    
    @kernel_function(description="Show the owners of a specific group by its object ID.")
    async def get_group_owners(self, group_id: str) -> str:
        """
        Fetches the list of users who are owners of the given group.
        """
        url = f"{self.graph_base_url}/groups/{group_id}/owners"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return f"❌ Error fetching owners for group '{group_id}': {resp.status_code} – {resp.text}"

        owners = resp.json().get("value", [])
        if not owners:
            return f"ℹ️ Group '{group_id}' has no owners."
        lines = [f"- {o.get('displayName')} ({o.get('userPrincipalName', o.get('mailNickname',''))})"
                 for o in owners]
        return "\n".join(lines)
    
    @kernel_function(description="Show the members of a specific group by its object ID.")
    async def get_group_members(self, group_id: str) -> str:
        """
        Fetches the list of users who are members of the given group.
        """
        url = f"{self.graph_base_url}/groups/{group_id}/members"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return f"❌ Error fetching members for group '{group_id}': {resp.status_code} – {resp.text}"

        members = resp.json().get("value", [])
        if not members:
            return f"ℹ️ Group '{group_id}' has no members."
        lines = [f"- {m.get('displayName')} ({m.get('userPrincipalName', m.get('mailNickname',''))})"
                 for m in members]
        return "\n".join(lines)

    @kernel_function(description="Count the total number of groups that have no owners in Entra ID.")
    async def count_ownerless_groups(self) -> str:
        """
        Lists all groups and counts how many have zero owners.
        """
        # 1) Retrieve all groups
        url = f"{self.graph_base_url}/groups?$select=id,displayName"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return f"❌ Error listing groups: {resp.status_code} – {resp.text}"

        groups = resp.json().get("value", [])
        ownerless = []

        # 2) Check owners for each group
        for g in groups:
            gid = g["id"]
            owners_resp = requests.get(f"{self.graph_base_url}/groups/{gid}/owners",
                                       headers=self._headers)
            if owners_resp.status_code != 200:
                # skip groups we can’t query
                continue
            if not owners_resp.json().get("value"):
                ownerless.append(g["displayName"])

        count = len(ownerless)
        if count == 0:
            return "ℹ️ Every group has at least one owner."
        lines = [f"- {name}" for name in ownerless]
        return f"Total ownerless groups: {count}\n" + "\n".join(lines)

    @kernel_function(description="Update a field for an existing group in Entra ID.")
    async def update_group(self, group_id: str, field: str, value: str) -> str:
        """
        Updates a single property of a group (e.g., displayName, mailNickname).
        """
        url = f"{self.graph_base_url}/groups/{group_id}"
        payload = {field: value}
        resp = requests.patch(url, headers=self._headers, json=payload)
        if resp.status_code == 204:
            return f"✅ Updated group '{group_id}': set {field} = {value}"
        return f"❌ Error updating group '{group_id}': {resp.status_code} – {resp.text}"
    
    @kernel_function(description="List given number ownerless groups in Entra ID.")
    async def list_ownerless_groups(self, max_results: int) -> str:
        """
        Fetches groups in pages and returns up to `max_results` group display names
        for which no owners are defined.
        """
        # Fetch a batch of groups at a time (Graph allows up to 999 per page)
        page_size = min(max_results * 5, 999)
        url = f"{self.graph_base_url}/groups?$select=id,displayName&$top={page_size}"
        ownerless = []

        # Iterate pages until we have enough ownerless groups or run out of pages
        while url and len(ownerless) < max_results:
            resp = requests.get(url, headers=self._headers)
            if resp.status_code != 200:
                return f"❌ Error fetching groups: {resp.status_code} – {resp.text}"

            payload = resp.json()
            for g in payload.get("value", []):
                if len(ownerless) >= max_results:
                    break

                # Check owners for this group
                owners_resp = requests.get(
                    f"{self.graph_base_url}/groups/{g['id']}/owners",
                    headers=self._headers
                )
                if owners_resp.status_code != 200:
                    # skip on error
                    continue

                if not owners_resp.json().get("value"):
                    ownerless.append(g["displayName"])

            # Follow nextLink if more pages remain
            url = payload.get("@odata.nextLink")

        if not ownerless:
            return "ℹ️ No ownerless groups found."

        # Format as a markdown-style list
        lines = [f"- {name}" for name in ownerless]
        return "\n".join(lines)