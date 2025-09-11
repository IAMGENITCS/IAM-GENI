import os
import requests
from dotenv import load_dotenv
from semantic_kernel.functions import kernel_function
from azure.identity import DefaultAzureCredential
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE


load_dotenv()

class AD_Provisioning_Agent:
    def __init__(self):
        print("🔧 Initializing AD Provisioning Agent...")
        self.username = os.getenv('AD_USERNAME')
        self.password = os.getenv('AD_PASSWORD')
        self.server = Server(os.getenv("AD_Server"), get_info=ALL)
        self.conn = Connection(self.server, user=self.username, password=self.password, auto_bind=True)
        self.base_dn = os.getenv("AD_Base_DN")
        # print("Connected to AD Server", self.conn.bind)
        print("Connected to AD Server")
        print("✅ AD Provisioning Agent ready.\n")

    @kernel_function(description="List all users in Active Directory.")
    async def list_users(self, count: int = 10) -> str:
        """
        Lists up to 'count' users from Active Directory.
        """
        self.conn.search(
            search_base=self.base_dn,
            search_filter='(objectClass=person)',
            attributes=['cn', 'mail']
        )

        if not self.conn.entries:
            return "ℹ️ No users found."

        # Limit the number of entries returned
        limited_entries = self.conn.entries[:count]

        lines = [
            f"- {entry.cn.value} ({entry.mail.value if entry.mail else 'No email'})"
            for entry in limited_entries
        ]
        return f"Showing {len(lines)} users:\n" + "\n".join(lines) 

    @kernel_function(description="Get details for a specific user by CN.")
    async def get_user_details(self, common_name: str) -> str:
        """
        Fetches details of a user given their common name (CN).
        """
        search_filter = f'(&(objectClass=person)(cn={common_name}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=['cn', 'mail', 'department', 'title','memberOf']
        )

        if not self.conn.entries:
            return f"❌ No user found with CN '{common_name}'."

        entry = self.conn.entries[0]
        details = [
            f"👤 Common Name: {entry.cn.value}",
            f"📧 Email: {entry.mail.value if entry.mail else 'N/A'}",
            f"🏢 Department: {entry.department.value if entry.department else 'N/A'}",
            f"🧑‍💼 Title: {entry.title.value if entry.title else 'N/A'}",
            f"👥 Member Of: {', '.join(entry.memberOf) if entry.memberOf else 'N/A'}",
            
        ]
        return "\n".join(details)
    
    @kernel_function(description="Create a new user in Active Directory.")
    async def create_user(self,
                          common_name: str="",
                          user_principal_name: str="",
                          password: str="") -> str:
        """
        Creates a new user in Active Directory.
        """
        dn = f"CN={common_name},OU=TestUsers,{self.base_dn}"
        attributes = {
            'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
            'cn': common_name,
            'userPrincipalName': user_principal_name,
            'sAMAccountName': user_principal_name.split("@")[0],
            'userPassword': password,
            'displayName': common_name,
            'mail': user_principal_name
        }

        if self.conn.add(dn, attributes=attributes):
            # Enable the account
            self.conn.modify(dn, {'userAccountControl': [(MODIFY_REPLACE, [512])]})
            return f"✅ User '{common_name}' created."
        else:
            return f"❌ Error creating user: {self.conn.result['description']} – {self.conn.result['message']}"
        
    @kernel_function(description="Update a field for an existing user.")
    async def update_user(self,
                          common_name: str,
                          field: str,
                          value: str) -> str:
        """
        Updates a specified field for a user identified by their common name (CN).
        """
        search_filter = f'(&(objectClass=person)(cn={common_name}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No user found with CN '{common_name}'."

        dn = self.conn.entries[0].entry_dn
        if self.conn.modify(dn, {field: [(MODIFY_REPLACE, [value])]}):
            return f"✅ Updated user '{common_name}': set {field} = {value}"
        else:
            return f"❌ Error updating user: {self.conn.result['description']} – {self.conn.result['message']}" 

    @kernel_function(description="Delete a user from Active Directory.")
    async def delete_user(self, common_name: str) -> str:
        """
        Deletes a user from Active Directory by their common name (CN).
        """
        search_filter = f'(&(objectClass=person)(cn={common_name}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No user found with CN '{common_name}'."

        dn = self.conn.entries[0].entry_dn
        if self.conn.delete(dn):
            return f"✅ User '{common_name}' deleted."
        else:
            return f"❌ Error deleting user: {self.conn.result['description']} – {self.conn.result['message']}" 

    #=======================Group Management Operations ================================

    @kernel_function(
        description="List a specified number of groups from Active Directory.",
        name="ListGroups"
    )
    async def list_groups(self, count: int = 10) -> str:
        """
        Lists up to 'count' groups from Active Directory.
        """
        self.conn.search(
            search_base=self.base_dn,
            search_filter='(objectClass=group)',
            attributes=['cn', 'description']
        )

        if not self.conn.entries:
            return "ℹ️ No groups found."

        limited_entries = self.conn.entries[:count]

        lines = [
            f"- {entry.cn.value} ({entry.description.value if entry.description else 'No description'})"
            for entry in limited_entries
        ]
        return f"Showing {len(lines)} groups:\n" + "\n".join(lines)

    @kernel_function(description="Get details for a specific group by CN.")
    async def get_group_details(self, common_name: str) -> str:
        """
        Fetches details of a group given its common name (CN).
        """
        search_filter = f'(&(objectClass=group)(cn={common_name}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=['cn', 'description', 'member', 'managedBy']
        )

        if not self.conn.entries:
            return f"❌ No group found with CN '{common_name}'."

        entry = self.conn.entries[0]
        details = [
            f"👥 Common Name: {entry.cn.value}",
            f"📝 Description: {entry.description.value if entry.description else 'N/A'}",
            f"👤 Members: {', '.join(entry.member) if entry.member else 'N/A'}"
            f"🧑‍💼 Owner: {entry.managedBy.value if entry.managedBy else 'N/A'}",
        ]
        return "\n".join(details)
    
    @kernel_function(description="Create a new group in Active Directory.")
    async def create_group(self,
                           common_name: str="",
                           description: str="") -> str:
        """
        Creates a new group in Active Directory.
        """
        dn = f"CN={common_name},OU=TestUsers,{self.base_dn}"
        attributes = {
            'objectClass': ['top', 'group'],
            'cn': common_name,
            'sAMAccountName': common_name,
            'description': description
        }

        if self.conn.add(dn, attributes=attributes):
            return f"✅ Group '{common_name}' created."
        else:
            return f"❌ Error creating group: {self.conn.result['description']} – {self.conn.result['message']}"  

    @kernel_function(description="show owner of a group from Active Directory.") 
    async def show_group_owner(self, common_name: str) -> str:
        """
        Shows the owner of a group identified by its common name (CN).
        """
        search_filter = f'(&(objectClass=group)(cn={common_name}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=['managedBy']
        )

        if not self.conn.entries:
            return f"❌ No group found with CN '{common_name}'."

        entry = self.conn.entries[0]
        owner = entry.managedBy.value if entry.managedBy else 'N/A'
        return f"🧑‍💼 Owner of group '{common_name}': {owner}"
    
    @kernel_function(description="show members of a group from Active Directory.")
    async def show_group_members(self, common_name: str) -> str:
        """
        Shows the members of a group identified by its common name (CN).
        """
        search_filter = f'(&(objectClass=group)(cn={common_name}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=['member']
        )

        if not self.conn.entries:
            return f"❌ No group found with CN '{common_name}'."

        entry = self.conn.entries[0]
        members = entry.member if entry.member else []
        if not members:
            return f"ℹ️ No members found in group '{common_name}'."
        
        # Step 2: Resolve each member and check status
        results = []
        for member_dn in members:
            self.conn.search(
                search_base=member_dn,
                search_filter='(objectClass=user)',
                attributes=['cn', 'userAccountControl']
            )

            if not self.conn.entries:
                results.append(f"- Unknown user: {member_dn}")
                continue

            user_entry = self.conn.entries[0]
            cn = user_entry.cn.value
            uac = int(user_entry.userAccountControl.value)

            # Step 3: Interpret account status
            is_disabled = bool(uac & 0x2)  # 0x2 = ACCOUNTDISABLE
            status = "❌ Disabled" if is_disabled else "✅ Active"

            results.append(f"- {cn}: {status}")

        return f"👥 Members of group '{common_name}':\n" + "\n".join(results)

    @kernel_function(description="Assign owner to a group in  Active Directory.")
    async def assign_group_owner(self,
                                 group_cn: str,
                                 owner_cn: str) -> str:
        """
        Assigns an owner to a group in Active Directory.
        """
        # Search for the group to get its DN
        group_search_filter = f'(&(objectClass=group)(cn={group_cn}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=group_search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No group found with CN '{group_cn}'."

        group_dn = self.conn.entries[0].entry_dn

        # Search for the user to get their DN
        user_search_filter = f'(&(objectClass=person)(cn={owner_cn}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=user_search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No user found with CN '{owner_cn}'."

        user_dn = self.conn.entries[0].entry_dn

        # Modify the group to set the managedBy attribute
        if self.conn.modify(group_dn, {'managedBy': [(MODIFY_REPLACE, [user_dn])]}):
            return f"✅ Assigned '{owner_cn}' as owner of group '{group_cn}'."
        else:
            return f"❌ Error assigning owner: {self.conn.result['description']} – {self.conn.result['message']}"   
        
    @kernel_function(description="Add user to a group in Active Directory.")
    async def add_user_to_group(self,
                                user_cn: str,
                                group_cn: str) -> str:
        """
        Adds a user to a group in Active Directory.
        """
        # Search for the group to get its DN
        group_search_filter = f'(&(objectClass=group)(cn={group_cn}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=group_search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No group found with CN '{group_cn}'."

        group_dn = self.conn.entries[0].entry_dn

        # Search for the user to get their DN
        user_search_filter = f'(&(objectClass=person)(cn={user_cn}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=user_search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No user found with CN '{user_cn}'."

        user_dn = self.conn.entries[0].entry_dn

        # Modify the group to add the user to the member attribute
        if self.conn.modify(group_dn, {'member': [(MODIFY_REPLACE, [user_dn])]}):
            return f"✅ Added user '{user_cn}' to group '{group_cn}'."
        else:
            return f"❌ Error adding user to group: {self.conn.result['description']} – {self.conn.result['message']}"      
        
    @kernel_function(description="Remove a user from a group in Active Directory.")
    async def remove_user_from_group(self,
                                     user_cn: str,
                                     group_cn: str) -> str:
        """
        Removes a user from a group in Active Directory.
        """
        # Search for the group to get its DN
        group_search_filter = f'(&(objectClass=group)(cn={group_cn}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=group_search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No group found with CN '{group_cn}'."

        group_dn = self.conn.entries[0].entry_dn

        # Search for the user to get their DN
        user_search_filter = f'(&(objectClass=person)(cn={user_cn}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=user_search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No user found with CN '{user_cn}'."

        user_dn = self.conn.entries[0].entry_dn

        # Modify the group to remove the user from the member attribute
        if self.conn.modify(group_dn, {'member': [(MODIFY_REPLACE, [])]}):
            return f"✅ Removed user '{user_cn}' from group '{group_cn}'."
        else:
            return f"❌ Error removing user from group: {self.conn.result['description']} – {self.conn.result['message']}"                                
    
    @kernel_function(description="Delete a group from Active Directory.")
    async def delete_group(self, common_name: str) -> str:
        """
        Deletes a group from Active Directory by its common name (CN).
        """
        search_filter = f'(&(objectClass=group)(cn={common_name}))'
        self.conn.search(
            search_base=self.base_dn,
            search_filter=search_filter,
            attributes=['cn']
        )

        if not self.conn.entries:
            return f"❌ No group found with CN '{common_name}'."

        dn = self.conn.entries[0].entry_dn
        if self.conn.delete(dn):
            return f"✅ Group '{common_name}' deleted."
        else:
            return f"❌ Error deleting group: {self.conn.result['description']} – {self.conn.result['message']}" 

    @kernel_function(description="list ownerless group from Active Directory.")  
    async def list_ownerless_groups(self) -> str:
        """
        Lists all groups in Active Directory that do not have an assigned owner (managedBy attribute is empty).
        """
        self.conn.search(
            search_base=self.base_dn,
            search_filter='(&(objectClass=group)(!(managedBy=*)))',
            attributes=['cn', 'description']
        )

        if not self.conn.entries:
            return "ℹ️ No ownerless groups found."

        lines = [
            f"- {entry.cn.value} ({entry.description.value if entry.description else 'No description'})"
            for entry in self.conn.entries
        ]
        return f"👥 Ownerless groups:\n" + "\n".join(lines) 

        
if __name__ == "__main__":
    agent = AD_Provisioning_Agent()
