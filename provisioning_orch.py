import os
import requests
from dotenv import load_dotenv
from semantic_kernel.functions import kernel_function
from azure.identity import DefaultAzureCredential
from azure.identity import AzureCliCredential
from datetime import datetime, timedelta
 
load_dotenv()
 
class ProvisioningAgent:
    def __init__(self):
        print("🔧 Initializing Provisioning Agent...")
        # Acquire token for Graph
        # self.credential = DefaultAzureCredential()
        self.credential = AzureCliCredential()
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
    

    @kernel_function(description="List Entra ID groups whose owners are inactive. Only includes groups that have owners.")
    async def list_groups_with_inactive_owners(self, limit: int = 0, count_only: bool = False) -> str:
        groups_url = f"{self.graph_base_url}/groups?$select=id,displayName"
        groups_resp = requests.get(groups_url, headers=self._headers)
        if groups_resp.status_code != 200:
            return f"❌ Error fetching groups: {groups_resp.status_code} – {groups_resp.text}"

        groups = groups_resp.json().get("value", [])
        inactive_groups = []

        for group in groups:
            group_id = group["id"]
            group_name = group["displayName"]

            owners_url = f"{self.graph_base_url}/groups/{group_id}/owners?$select=id,userPrincipalName,accountEnabled"
            owners_resp = requests.get(owners_url, headers=self._headers)
            if owners_resp.status_code != 200:
                continue  # skip if owners can't be fetched

            owners = owners_resp.json().get("value", [])

            # ✅ Skip groups with no owners
            if not owners:
                continue

            # ✅ Check if all owners are inactive
            active_owners = [o for o in owners if o.get("accountEnabled", True)]
            if not active_owners:
                inactive_groups.append(f"🚫 {group_name} (ID: {group_id})")

        if count_only:
            return f"🔢 Total groups with inactive owners: {len(inactive_groups)}"

        if not inactive_groups:
            return "✅ All groups with owners have at least one active owner."

        if limit > 0:
            inactive_groups = inactive_groups[:limit]

        return "\n".join(inactive_groups)


    @kernel_function(description="List guest users who haven't signed in for the last 90 days. Returns count or top N users.")
    async def list_inactive_guest_users(self, limit: int = 5, count_only: bool = False) -> str:
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        url = f"{self.graph_base_url}/users?$filter=userType eq 'Guest'&$select=displayName,userPrincipalName,signInActivity&$top=999"

        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return f"❌ Error fetching guest users: {resp.status_code} – {resp.text}"

        users = resp.json().get("value", [])
        inactive_guests = []

        for user in users:
            sign_in = user.get("signInActivity", {}).get("lastSignInDateTime")
            if not sign_in:
                inactive_guests.append(f"🕸️ {user['displayName']} ({user['userPrincipalName']}) — Never signed in")
                continue

            try:
                last_sign_in = datetime.strptime(sign_in, "%Y-%m-%dT%H:%M:%SZ")
                if last_sign_in < cutoff_date:
                    inactive_guests.append(f"⏳ {user['displayName']} ({user['userPrincipalName']}) — Last sign-in: {sign_in}")
            except Exception:
                continue  # skip malformed dates

        if count_only:
            return f"🔢 Total inactive guest users (90+ days): {len(inactive_guests)}"

        if not inactive_guests:
            return "✅ All guest users have signed in within the last 90 days."

        return "\n".join(inactive_guests[:limit])
    

    @kernel_function(description="List users blocked by location-based Conditional Access policies in their sign-ins.")
    async def get_users_blocked_by_location_ca(self) -> str:
        url = f"{self.graph_base_url}/auditLogs/signIns?$filter=status/errorCode eq 53003 and conditionalAccessStatus eq 'failure'"
        users_blocked = []

        while url:
            resp = requests.get(url, headers=self._headers)
            if resp.status_code != 200:
                return f"❌ Error fetching sign-in logs: {resp.status_code} – {resp.text}"

            data = resp.json()
            for signin in data.get("value", []):
                applied_policies = signin.get("appliedConditionalAccessPolicies", [])
                # Filter for policies that look like location-based
                failing_policies = [
                    p.get("displayName") for p in applied_policies if p.get("result") == "failure"
                ]
                if any("location" in (p or "").lower() for p in failing_policies):
                    users_blocked.append({
                        "userPrincipalName": signin.get("userPrincipalName"),
                        "userId": signin.get("userId"),
                        "time": signin.get("createdDateTime"),
                        "policies": failing_policies
                    })

            url = data.get("@odata.nextLink")  # pagination

        if not users_blocked:
            return "✅ No users were blocked by location-based Conditional Access policies."

        # Return a summarized string (could also return JSON if you prefer structured output)
        summary = "\n".join(
            f"- {u['userPrincipalName']} at {u['time']} (Policies: {', '.join(u['policies'])})"
            for u in users_blocked[:20]  # limit to first 20 for readability
        )
        return f"🚫 Users blocked by location-based CA policies:\n{summary}"
    
    @kernel_function(description="List Entra ID administrators who have not registered Certificate-based authentication.")
    async def get_admins_without_cba(self) -> str:
        # Step 1: Get Global Administrators role
        roles_url = f"{self.graph_base_url}/directoryRoles/bbda4080-69bb-4b2d-bbaf-f0526515c6b9"
        roles_resp = requests.get(roles_url, headers=self._headers)
        if roles_resp.status_code != 200:
            return f"❌ Error fetching roles: {roles_resp.status_code} – {roles_resp.text}"
        roles = roles_resp.json().get("value", [])
        if not roles:
            return "No Global Administrator role found."
        role_id = roles[0]["id"]

        # Step 2: Get members of the GA role
        members_url = f"{self.graph_base_url}/directoryRoles/{role_id}/members"
        members_resp = requests.get(members_url, headers=self._headers)
        if members_resp.status_code != 200:
            return f"❌ Error fetching role members: {members_resp.status_code} – {members_resp.text}"
        members = members_resp.json().get("value", [])

        no_cba = []
        for m in members:
            user_id = m.get("id")
            upn = m.get("userPrincipalName", "unknown")

            # Step 3: Get auth methods for this user
            methods_url = f"{self.graph_base_url}/users/{user_id}/authentication/methods"
            methods_resp = requests.get(methods_url, headers=self._headers)
            if methods_resp.status_code != 200:
                continue

            methods = methods_resp.json().get("value", [])
            has_cba = any(
                meth.get("@odata.type") == "#microsoft.graph.x509CertificateAuthenticationMethod"
                for meth in methods
            )
            if not has_cba:
                no_cba.append(upn)

        if not no_cba:
            return "✅ All Global Administrators have registered Certificate-based authentication."

        return "🚫 Admins without CBA:\n" + "\n".join(f"- {u}" for u in no_cba)