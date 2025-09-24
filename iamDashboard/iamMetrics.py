import os
import requests
import json
from dotenv import load_dotenv
from semantic_kernel.functions import kernel_function
from azure.identity import ClientSecretCredential 
from ldap3 import Server, Connection, ALL, SUBTREE
from datetime import datetime, timedelta, timezone

load_dotenv()

# ---------- Utility for AD ----------
def datetime_to_filetime(dt):
    """Convert datetime -> Windows FileTime (used for lastLogonTimestamp)."""
    epoch_start = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return int((dt - epoch_start).total_seconds() * 10**7)

# ---------- IAM Plugin ----------
class IAMPlugin:
    def __init__(self):
        print("🔧 Initializing IAM Plugin...")

        # Entra connection
        self.credential = ClientSecretCredential(
            tenant_id=os.environ["TENANT_ID"],
            client_id=os.environ["CLIENT_ID_DASHBOARD"],
            client_secret=os.environ["CLIENT_SECRET_DASHBOARD"]
        )
        token = self.credential.get_token("https://graph.microsoft.com/.default")
        self._headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }

        # AD connection
        self.username = os.getenv("AD_USERNAME")
        self.password = os.getenv("AD_PASSWORD")
        self.server = Server(os.getenv("AD_SERVER"), get_info=ALL)
        self.conn = Connection(
            self.server,
            user=self.username,
            password=self.password,
            auto_bind=True
        )
        self.base_dn = os.getenv("AD_BASE_DN")

        print("✅ IAM Plugin ready.")

    # ----------- Entra ID Dashboard Metrics -----------

    @kernel_function(description="Get risky users in Entra ID")
    async def get_risky_users(self):
        url = "https://graph.microsoft.com/v1.0/identityProtection/riskyUsers?$filter=riskLevel eq 'high'"
        resp = requests.get(url, headers=self._headers)
        return resp.json()

    @kernel_function(description="Get protected users in Entra ID")
    async def get_protected_users(self):
        url = ("https://graph.microsoft.com/v1.0/identityProtection/riskDetections?"
               "$filter=riskState eq 'dismissed' or riskState eq 'remediated'")
        resp = requests.get(url, headers=self._headers)
        return resp.json()

    @kernel_function(description="Get privileged accounts with Global Admin access")
    async def get_privileged_accounts(self):
        role_id = "bbda4080-69bb-4b2d-bbaf-f0526515c6b9"  # Global Administrator role ID
        url = f"https://graph.microsoft.com/v1.0/directoryRoles/{role_id}/members?$select=displayName,id,userPrincipalName"
        resp = requests.get(url, headers=self._headers)
        return resp.json()

    @kernel_function(description="Get ownerless groups in Entra ID")
    async def get_ownerless_groups(self):
        groups_url = "https://graph.microsoft.com/v1.0/groups?$select=id,displayName"
        resp = requests.get(groups_url, headers=self._headers)
        groups = resp.json().get("value", [])
        ownerless = []
        for g in groups:
            owners_url = f"https://graph.microsoft.com/v1.0/groups/{g['id']}/owners?$count=true"
            o_resp = requests.get(
                owners_url,
                headers={**self._headers, "ConsistencyLevel": "eventual"}
            )
            if len(o_resp.json().get("value", [])) == 0:
                ownerless.append({"id": g["id"], "displayName": g["displayName"]})
        return {"value": ownerless}

    @kernel_function(description="Get applications where MFA is not enabled")
    async def get_mfa_disabled_apps(self):
        url = "https://graph.microsoft.com/v1.0/servicePrincipals?$select=id,appId,displayName"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return {"error": f"❌ Error fetching applications: {resp.status_code} – {resp.text}"}
        
        apps = resp.json().get("value", [])
        all_app_map = {app["id"]: app.get("displayName", "Unnamed App") for app in apps}

        # Get Conditional Access policies
        url = "https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code != 200:
            return {"error": f"❌ Error fetching CA policies: {resp.status_code} – {resp.text}"}

        policies = resp.json().get("value", [])
        mfa_apps = set()

        for policy in policies:
            grant_controls = policy.get("grantControls")
            if grant_controls and "builtInControls" in grant_controls:
                if "mfa" in grant_controls.get("builtInControls", []):
                    conditions = policy.get("conditions", {}).get("applications", {})
                    include = conditions.get("includeApplications", [])
                    exclude = set(conditions.get("excludeApplications", []))

                    if "All" in include:
                        policy_apps = set(all_app_map.keys()) - exclude
                    else:
                        policy_apps = set(include) - exclude

                    mfa_apps.update(policy_apps)

        apps_without_mfa = [
            {"id": app_id, "displayName": name}
            for app_id, name in all_app_map.items()
            if app_id not in mfa_apps
        ]

        return {"count": len(apps_without_mfa), "apps_without_mfa": apps_without_mfa}

    # ----------- AD Dashboard Metrics -----------

    def list_ownerless_groups_ad(self):
        """List AD groups without an owner (managedBy empty)."""
        self.conn.search(
            search_base=self.base_dn,
            search_filter="(&(objectClass=group)(!(managedBy=*)))",
            attributes=["cn", "description"]
        )
        return [
            {
                "cn": entry.cn.value,
                "description": entry.description.value if entry.description else "No description"
            }
            for entry in self.conn.entries
        ]

    def count_memberless_groups(self, max_results=None, page_size=500):
        """Count AD groups with no members."""
        filter_str = "(&(objectClass=group)(!(member=*)))"
        attrs = ["distinguishedName", "cn"]

        total = 0
        results = []
        cookie = None

        while True:
            self.conn.search(
                search_base=self.base_dn,
                search_filter=filter_str,
                search_scope=SUBTREE,
                attributes=attrs,
                paged_size=page_size,
                paged_cookie=cookie
            )
            for entry in self.conn.entries:
                total += 1
                if max_results is None or len(results) < max_results:
                    results.append({"dn": entry.distinguishedName.value, "cn": entry.cn.value})

            cookie = (
                self.conn.result.get("controls", {})
                .get("1.2.840.113556.1.4.319", {})
                .get("value", {})
                .get("cookie")
            )
            if not cookie:
                break

        return {"count": total, "sample": results}

    def find_inactive_accounts(self, days=30, max_results=None):
        """Find AD accounts inactive > X days (ignores disabled)."""
        threshold_dt = datetime.now(timezone.utc) - timedelta(days=days)
        threshold_filetime = datetime_to_filetime(threshold_dt)

        ldap_filter = (
            f"(&(objectClass=user)(objectCategory=person)"
            f"(lastLogonTimestamp<={threshold_filetime})"
            f"(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
        )

        self.conn.search(
            search_base=self.base_dn,
            search_filter=ldap_filter,
            search_scope=SUBTREE,
            attributes=["sAMAccountName", "displayName", "lastLogonTimestamp"],
            paged_size=500
        )

        results = []
        for entry in self.conn.entries:
            if max_results and len(results) >= max_results:
                break
            results.append({
                "sam": entry.sAMAccountName.value,
                "name": entry.displayName.value,
                "lastLogonTimestamp": entry.lastLogonTimestamp.value
            })

        return {"count": len(self.conn.entries), "sample": results}

    def count_service_accounts(self, max_results=50):
        """Count AD service accounts (SPN set)."""
        ldap_filter = "(&(objectClass=user)(servicePrincipalName=*))"
        attrs = ["sAMAccountName", "distinguishedName"]

        self.conn.search(
            search_base=self.base_dn,
            search_filter=ldap_filter,
            search_scope=SUBTREE,
            attributes=attrs,
            paged_size=500
        )
        total = len(self.conn.entries)
        sample = [{"sam": e.sAMAccountName.value, "dn": e.distinguishedName.value}
                  for e in self.conn.entries[:max_results]]
        return {"count": total, "sample": sample}

    def count_password_never_expire_accounts(self, max_results=50):
        """Count AD accounts where password never expires."""
        ldap_filter = "(&(objectCategory=person)(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=65536))"
        attrs = ["sAMAccountName", "displayName", "distinguishedName", "userAccountControl"]
        page_size = 500

        total = 0
        sample = []
        cookie = None

        while True:
            self.conn.search(
                search_base=self.base_dn,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=attrs,
                paged_size=page_size,
                paged_cookie=cookie,
            )
            for entry in self.conn.entries:
                total += 1
                if len(sample) < max_results:
                    sample.append({
                        "sam": entry.sAMAccountName.value,
                        "displayName": getattr(entry, "displayName", None),
                        "dn": entry.distinguishedName.value,
                    })

            cookie = (
                self.conn.result.get("controls", {})
                .get("1.2.840.113556.1.4.319", {})
                .get("value", {})
                .get("cookie")
            )
            if not cookie:
                break

        return {"count": total, "sample": sample}
    

    def count_account_lockouts(self, max_results=50):
        """Count AD accounts currently locked out (lockoutTime >= 1)."""
        ldap_filter = "(&(objectCategory=person)(objectClass=user)(lockoutTime>=1))"
        attrs = ["sAMAccountName", "displayName", "distinguishedName", "lockoutTime"]

        self.conn.search(
            search_base=self.base_dn,
            search_filter=ldap_filter,
            search_scope=SUBTREE,
            attributes=attrs,
            paged_size=500
        )

        results = []
        for entry in self.conn.entries[:max_results]:
            lockout_raw = entry.lockoutTime.value
            lockout_dt = None
            if lockout_raw:
                try:
                    lockout_dt = (datetime(1601, 1, 1, tzinfo=timezone.utc) +
                                  timedelta(microseconds=int(lockout_raw) // 10))
                except Exception:
                    lockout_dt = None

            results.append({
                "sam": entry.sAMAccountName.value,
                "displayName": getattr(entry, "displayName", None),
                "dn": entry.distinguishedName.value,
                "lockoutTime_raw": lockout_raw,
                "lockoutTime": lockout_dt.isoformat() if lockout_dt else None
            })

        return {"count": len(self.conn.entries), "sample": results}

    # ----------- Dashboard Aggregator -----------

    @kernel_function(description="Build IAM dashboard from all data sources")
    async def build_iam_dashboard(self):
        return {
            # Entra ID
            "risky_users": await self.get_risky_users(),
            "protected_users": await self.get_protected_users(),
            "privileged_accounts": await self.get_privileged_accounts(),
            "ownerless_groups_entra": await self.get_ownerless_groups(),
            "mfa_disabled_apps": await self.get_mfa_disabled_apps(),

            # AD
            "ownerless_groups_ad": self.list_ownerless_groups_ad(),
            "memberless_groups": self.count_memberless_groups(max_results=10),
            "inactive_accounts": self.find_inactive_accounts(days=90, max_results=10),
            "service_accounts": self.count_service_accounts(max_results=10),
            "pwd_never_expire": self.count_password_never_expire_accounts(max_results=10),
            "account_lockouts": self.count_account_lockouts(max_results=10)
        }
