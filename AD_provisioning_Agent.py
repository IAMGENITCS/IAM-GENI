import os
import requests
from dotenv import load_dotenv
from semantic_kernel.functions import kernel_function
from azure.identity import DefaultAzureCredential
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE,MODIFY_ADD, MODIFY_DELETE

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

            attributes=['cn', 'description', 'member', 'managedBy','whenCreated']

        )

        if not self.conn.entries:

            return f"❌ No group found with CN '{common_name}'."

         # Get creation date


        entry = self.conn.entries[0]

        details = [

            f"👥 Common Name: {entry.cn.value}",

            f"📝 Description: {entry.description.value if entry.description else 'N/A'}",

            f"👤 Members: {', '.join(entry.member) if entry.member else 'N/A'}",

            f"🧑‍💼 Owner: {entry.managedBy.value if entry.managedBy else 'N/A'}",

            f"🗓 Created on: {entry.whenCreated.value if entry.whenCreated else 'N/A'}"

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



    @kernel_function(description="Show the owner of a group from Active Directory (only CN).")

    async def show_group_owner(self, common_name: str) -> str:

        """

        Shows the owner of a group identified by its common name (CN),

        displaying only the group CN and the owner's CN.

        """

        # Step 1: Find the group

        search_filter = f'(&(objectClass=group)(cn={common_name}))'

        self.conn.search(

            search_base=self.base_dn,

            search_filter=search_filter,

            attributes=['managedBy']

        )

        if not self.conn.entries:

            return f"❌ No group found with CN '{common_name}'."

        entry = self.conn.entries[0]

        owner_dn = entry.managedBy.value if entry.managedBy else None

        if not owner_dn:

            return f"ℹ️ Group '{common_name}' does not have an owner assigned."

        # Step 2: Extract owner's CN from DN

        owner_cn = owner_dn.split(',')[0].replace('CN=', '')

        return f"🧑‍💼 Owner of group '{common_name}': {owner_cn}"



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


    @kernel_function(description="Add user to a group in Active Directory without removing existing members.")

    async def add_user_to_group(self, user_cn: str, group_cn: str) -> str:

        """

        Adds a user to a group in Active Directory without removing existing members.

        """

        # Search for the group DN

        group_search_filter = f'(&(objectClass=group)(cn={group_cn}))'

        self.conn.search(

            search_base=self.base_dn,

            search_filter=group_search_filter,

            attributes=['cn']

        )

        if not self.conn.entries:

            return f"❌ No group found with CN '{group_cn}'."

        group_dn = self.conn.entries[0].entry_dn

        # Search for the user DN

        user_search_filter = f'(&(objectClass=person)(cn={user_cn}))'

        self.conn.search(

            search_base=self.base_dn,

            search_filter=user_search_filter,

            attributes=['cn']

        )

        if not self.conn.entries:

            return f"❌ No user found with CN '{user_cn}'."

        user_dn = self.conn.entries[0].entry_dn

        # Add user to group without removing existing members

        if self.conn.modify(group_dn, {'member': [(MODIFY_ADD, [user_dn])]}):

            return f"✅ Added user '{user_cn}' to group '{group_cn}' without affecting existing members."

        else:

            return f"❌ Error adding user to group: {self.conn.result['description']} – {self.conn.result['message']}"


    @kernel_function(description="Remove a user from a group in Active Directory without affecting other members.")

    async def remove_user_from_group(self, user_cn: str, group_cn: str) -> str:

        """

        Removes a user from a group in Active Directory safely, without affecting other members.

        """

        # Search for the group DN

        group_search_filter = f'(&(objectClass=group)(cn={group_cn}))'

        self.conn.search(

            search_base=self.base_dn,

            search_filter=group_search_filter,

            attributes=['cn', 'member']

        )

        if not self.conn.entries:

            return f"❌ No group found with CN '{group_cn}'."

        group_dn = self.conn.entries[0].entry_dn

        # Search for the user DN

        user_search_filter = f'(&(objectClass=person)(cn={user_cn}))'

        self.conn.search(

            search_base=self.base_dn,

            search_filter=user_search_filter,

            attributes=['cn']

        )

        if not self.conn.entries:

            return f"❌ No user found with CN '{user_cn}'."

        user_dn = self.conn.entries[0].entry_dn

        # Remove user from group without affecting other members

        if self.conn.modify(group_dn, {'member': [(MODIFY_DELETE, [user_dn])]}):

            return f"✅ Removed user '{user_cn}' from group '{group_cn}' safely."

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


    @kernel_function(description="List or count Active Directory groups without an owner.")

    async def groups_without_owner(self, action: str = "list", count: int = 0) -> str:

        """

        Handles Active Directory groups without an assigned owner (managedBy empty).

        Args:

            action (str): "list" → show groups, "count" → show total number, "both" → show both

            count (int): number of groups to show when listing (ignored for count only)

        Returns:

            str: Formatted result with list and/or count of ownerless groups

        """

        try:

            # Step 1: Search all groups where managedBy is empty

            self.conn.search(

                search_base=self.base_dn,

                search_filter='(&(objectClass=group)(!(managedBy=*)))',

                attributes=['cn', 'description']

            )

            if not self.conn.entries:

                return "✅ No ownerless groups found in Active Directory."

            ownerless_groups = [

                f"{entry.cn.value} ({entry.description.value if entry.description else 'No description'})"

                for entry in self.conn.entries

            ]

            total = len(ownerless_groups)

            # Limit results if requested

            limited_results = ownerless_groups[:count] if count > 0 else ownerless_groups

            # Step 2: Respond based on action

            if action.lower() == "count":

                return f"📊 Total ownerless groups: {total}"

            elif action.lower() == "list":

                return f"👥 Ownerless groups ({len(limited_results)} shown):\n" + "\n".join(f"- {g}" for g in limited_results)

            elif action.lower() == "both":

                return (

                    f"👥 Ownerless groups ({len(limited_results)} shown):\n"

                    + "\n".join(f"- {g}" for g in limited_results)

                    + f"\n\n📊 Total ownerless groups: {total}"

                )

            else:

                return "❌ Invalid action. Use 'list', 'count', or 'both'."

        except Exception as e:

            return f"❌ LDAP error: {str(e)}"


    @kernel_function(

        description=(

            "Update details of an Active Directory group. "

            "You can update one or more attributes: "

            "CN (group name), description, or owner (managedBy). "

            "The function will ask for the values of attributes you want to update."

        )

        )

    async def update_group_details(self, group_cn: str, new_cn: str = None, description: str = None, owner_cn: str = None) -> str:

        """

        Updates an AD group dynamically based on provided attributes:

        - CN → renames the group

        - description → updates the group's description

        - owner_cn → assigns a new owner

        """

        try:

            # Step 1: Find the group

            search_filter = f'(&(objectClass=group)(cn={group_cn}))'

            self.conn.search(

                search_base=self.base_dn,

                search_filter=search_filter,

                attributes=['cn', 'description', 'managedBy']

            )

            if not self.conn.entries:

                return f"❌ No group found with CN '{group_cn}'."

            group_dn = self.conn.entries[0].entry_dn

            result_messages = []

            # Step 2: Update description

            if description:

                if self.conn.modify(group_dn, {'description': [(MODIFY_REPLACE, [description])] }):

                    result_messages.append(f"✅ Updated description to: {description}")

                else:

                    result_messages.append(f"❌ Failed to update description: {self.conn.result['description']}")

            # Step 3: Update owner

            if owner_cn:

                # Find owner DN

                self.conn.search(

                    search_base=self.base_dn,

                    search_filter=f'(&(objectClass=person)(cn={owner_cn}))',

                    attributes=['cn']

                )

                if not self.conn.entries:

                    result_messages.append(f"❌ Owner CN '{owner_cn}' not found.")

                else:

                    owner_dn = self.conn.entries[0].entry_dn

                    if self.conn.modify(group_dn, {'managedBy': [(MODIFY_REPLACE, [owner_dn])] }):

                        result_messages.append(f"✅ Assigned new owner: {owner_cn}")

                    else:

                        result_messages.append(f"❌ Failed to assign owner: {self.conn.result['description']}")

            # Step 4: Update CN (rename)

            if new_cn and new_cn != group_cn:

                new_rdn = f"CN={new_cn}"

                if self.conn.modify_dn(group_dn, new_rdn):

                    result_messages.append(f"✅ Renamed group CN to: {new_cn}")

                else:

                    result_messages.append(f"❌ Failed to rename CN: {self.conn.result['description']}")

            if not result_messages:

                return "ℹ️ No updates were provided."

            else:

                return "\n".join(result_messages)

        except Exception as e:

            return f"❌ LDAP error: {str(e)}"



    @kernel_function(

        description="Displays the owner and creation date of an AD group."

    )

    async def get_group_info(self, group_cn: str) -> str:

        """

        Fetches creation date and owner CN for a specific AD group.

        """

        try:

            # Search for the group and request required attributes

            self.conn.search(

                search_base=self.base_dn,

                search_filter=f'(&(objectClass=group)(cn={group_cn}))',

                attributes=['cn', 'whenCreated', 'managedBy']

            )

            if not self.conn.entries:

                return f"❌ No group found with CN '{group_cn}'."

            entry = self.conn.entries[0]

            # Get creation date

            when_created = getattr(entry, 'whenCreated', None)

            creation_date = when_created.value if when_created else "N/A"

            # Get owner DN

            managed_by = getattr(entry, 'managedBy', None)

            if managed_by and managed_by.value:

                owner_dn = managed_by.value

                # Extract CN from DN (first CN component)

                owner_cn = owner_dn.split(',')[0].replace('CN=', '')

            else:

                owner_cn = "N/A"

            return (

                f"👥 Group: {group_cn}\n"

                f"🗓 Created on: {creation_date}\n"

                # f"👤 Owner: {owner_cn}"

            )

        except Exception as e:

            return f"❌ LDAP error: {str(e)}"


    @kernel_function(description="List or count Active Directory groups with zero members.")

    async def groups_with_no_members(self, action: str = "list", count: int = 0) -> str:

        try:

            self.conn.search(

                search_base=self.base_dn,

                search_filter='(&(objectClass=group))',

                attributes=['cn', 'member']

            )

            zero_member_groups = [g.cn.value for g in self.conn.entries if not g.member]

            total = len(zero_member_groups)

            limited = zero_member_groups[:count] if count > 0 else zero_member_groups

            if action.lower() == "count":

                return f"📊 Total groups with zero members: {total}"

            elif action.lower() == "list":

                return f"👥 Groups with zero members ({len(limited)} shown):\n" + "\n".join(f"- {g}" for g in limited)

            elif action.lower() == "both":

                return (

                    f"👥 Groups with zero members ({len(limited)} shown):\n"

                    + "\n".join(f"- {g}" for g in limited)

                    + f"\n\n📊 Total groups with zero members: {total}"

                )

            else:

                return "❌ Invalid action. Use 'list', 'count', or 'both'."

        except Exception as e:

            return f"❌ LDAP error: {str(e)}"
        

    @kernel_function(description="List or count Active Directory groups whose owners are inactive/disabled, with natural language prompt support.")

    async def inactive_owner_groups_nlp(self, prompt: str) -> str:

        """

        Handles AD groups whose owners are inactive or disabled based on a natural language prompt.

        Example prompts:

        - "List 5 groups whose owners are inactive"

        - "How many groups have inactive owners?"

        - "List all groups with disabled owners and show total count"

        Args:

            prompt (str): Natural language prompt

        Returns:

            str: Formatted output

        """

        try:

            # Step 1: Determine action and count from prompt

            action = "list"

            count = 0

            prompt_lower = prompt.lower()

            if "count" in prompt_lower or "how many" in prompt_lower or "total" in prompt_lower:

                if "list" in prompt_lower:

                    action = "both"

                else:

                    action = "count"

            elif "list" in prompt_lower:

                action = "list"

            import re

            match = re.search(r'\b(\d+)\b', prompt_lower)

            if match:

                count = int(match.group(1))

            # Step 2: Search for all groups with owners

            self.conn.search(

                search_base=self.base_dn,

                search_filter='(&(objectClass=group)(managedBy=*))',

                attributes=['cn', 'managedBy']

            )

            if not self.conn.entries:

                return "ℹ️ No groups with assigned owners found."

            inactive_owner_groups = []

            # Step 3: Check owner status for each group

            for group in self.conn.entries:

                group_cn = group.cn.value

                owner_dn = group.managedBy.value if group.managedBy else None

                if not owner_dn:

                    continue

                self.conn.search(

                    search_base=owner_dn,

                    search_filter='(objectClass=user)',

                    attributes=['cn', 'sAMAccountName', 'userAccountControl']

                )

                if not self.conn.entries:

                    continue

                owner_entry = self.conn.entries[0]

                uac = int(owner_entry.userAccountControl.value)

                # Check if owner is disabled (0x2 = ACCOUNTDISABLE)

                if uac & 0x2:

                    inactive_owner_groups.append(

                        f"- Group: {group_cn} | Owner: {owner_entry.cn.value} ({owner_entry.sAMAccountName.value}) ❌ Disabled"

                    )

            total = len(inactive_owner_groups)

            if total == 0:

                return "✅ No groups with inactive/disabled owners found."

            # Step 4: Apply count limit if needed

            limited_results = inactive_owner_groups[:count] if count > 0 else inactive_owner_groups

            # Step 5: Build response based on action

            if action == "count":

                return f"📊 Total groups with inactive/disabled owners: {total}"

            elif action == "list":

                return f"👥 Groups with inactive/disabled owners ({len(limited_results)} shown):\n" + "\n".join(limited_results)

            elif action == "both":

                return (

                    f"👥 Groups with inactive/disabled owners ({len(limited_results)} shown):\n"

                    + "\n".join(limited_results)

                    + f"\n\n📊 Total groups with inactive/disabled owners: {total}"

                )

            else:

                return "❌ Unable to determine action from prompt."

        except Exception as e:

            return f"❌ LDAP error: {str(e)}"

    @kernel_function(description="Check and list AD groups that do not follow specified naming conventions like SG_SAP, SG_Finance.")

    async def groups_not_following_naming_convention(self,

                                                    allowed_prefixes: list[str],

                                                    count: int = 0) -> str:

        """

        Lists AD groups whose CN does not start with any of the allowed prefixes.

        Args:

            allowed_prefixes (list[str]): Valid naming prefixes (e.g., ['SG_SAP', 'SG_Finance'])

            count (int): Max number of groups to list. If 0, prompt user to specify.

        Returns:

            str: Summary + optional list

        """

        try:

            # 🔍 Search all groups

            self.conn.search(

                search_base= f"OU=BU_Groups,{self.base_dn}",

                search_filter='(objectClass=group)',

                attributes=['cn', 'description']

            )

            if not self.conn.entries:

                return "ℹ️ No groups found in Active Directory."

            # 🧪 Filter non-compliant groups

            non_compliant = []

            for entry in self.conn.entries:

                cn = entry.cn.value

                if not any(cn.startswith(prefix) for prefix in allowed_prefixes):

                    desc = entry.description.value if entry.description else "No description"

                    non_compliant.append(f"- {cn} ({desc})")

            total = len(non_compliant)

            if total == 0:

                return "✅ All groups follow the specified naming conventions."

            # 🧾 Summary + optional listing

            summary = f"🚫 Total groups not following naming conventions: {total}"

            if count == 0:

                return summary + "\n\nℹ️ How many would you like to list?"

            else:

                limited = non_compliant[:count]

                return summary + f"\n\n📋 Showing {len(limited)} group(s):\n" + "\n".join(limited)

        except Exception as e:

            return f"❌ LDAP error: {str(e)}"


if __name__ == "__main__":

    agent = AD_Provisioning_Agent()  