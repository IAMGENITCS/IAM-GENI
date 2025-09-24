import asyncio
import streamlit as st
from iamMetrics import IAMPlugin 

# -----------------------------
# Cached wrapper for dashboard
# -----------------------------
@st.cache_data(ttl=21600)  # cache for 6 hours
def get_dashboard_cached():
    return asyncio.run(get_dashboard())

async def get_dashboard():
    plugin = IAMPlugin()
    return await plugin.build_iam_dashboard()

# Fetch data
dashboard = get_dashboard_cached()

st.set_page_config(page_title="IAM Security Dashboard", layout="wide")
st.title("🛡️ IAM Security Dashboard (Summary)")

# -----------------------------
# Extract Entra metrics
# -----------------------------
risky_data = dashboard.get("risky_users", {}).get("value", [])
protected_data = dashboard.get("protected_users", {}).get("value", [])
privileged_data = dashboard.get("privileged_accounts", {}).get("value", [])
ownerless_entra = dashboard.get("ownerless_groups_entra", {}).get("value", [])
mfa_apps = dashboard.get("mfa_disabled_apps", {})

# Handle MFA apps (string vs dict)
if isinstance(mfa_apps, str):
    mfa_count = 0 if "✅" in mfa_apps else mfa_apps.count("\n")
else:
    mfa_count = mfa_apps.get("count", 0)

# -----------------------------
# Extract AD metrics
# -----------------------------
ownerless_ad = dashboard.get("ownerless_groups_ad", [])
memberless_groups = dashboard.get("memberless_groups", {}).get("count", 0)
inactive_accounts = dashboard.get("inactive_accounts", {}).get("count", 0)
service_accounts = dashboard.get("service_accounts", {}).get("count", 0)
pwd_never_expire = dashboard.get("pwd_never_expire", {}).get("count", 0)
account_lockouts = dashboard.get("account_lockouts", {}).get("count", 0)   # 🔒 New

# -----------------------------
# Tile / Card Style Layout
# -----------------------------
tile_style = """
<style>
.metric-card {
    background-color: #f9f9f9;
    padding: 25px;
    border-radius: 15px;
    box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
    text-align: center;
    margin: 10px;
}
.metric-title {
    font-size: 16px;
    font-weight: bold;
    color: #444;
}
.metric-value {
    font-size: 26px;
    font-weight: bold;
    color: #2c7be5;
}
</style>
"""
st.markdown(tile_style, unsafe_allow_html=True)

# -----------------------------
# Entra ID Metrics
# -----------------------------
st.subheader("☁️ Entra ID Metrics")
entra_metrics = [
    ("🚨 Risky Users", len(risky_data)),
    ("🛡️ Protected Users", len(protected_data)),
    ("👑 Privileged Accounts", len(privileged_data)),
    ("👥 Ownerless Groups", len(ownerless_entra)),
    ("🔐 Apps without MFA", mfa_count),
]
for i in range(0, len(entra_metrics), 2):
    cols = st.columns(2)
    for j, col in enumerate(cols):
        if i + j < len(entra_metrics):
            title, value = entra_metrics[i + j]
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-title">{title}</div>
                        <div class="metric-value">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# -----------------------------
# Active Directory Metrics
# -----------------------------
st.subheader("🖥️ Active Directory Metrics")
ad_metrics = [
    ("👥 Ownerless Groups (AD)", len(ownerless_ad)),
    ("👥 Memberless Groups (AD)", memberless_groups),
    ("⏳ Inactive Accounts (90d+)", inactive_accounts),
    ("⚙️ Service Accounts", service_accounts),
    ("🔒 Password Never Expires", pwd_never_expire),
    ("🚫 Account Lockouts", account_lockouts),   # 🔒 Added
]
for i in range(0, len(ad_metrics), 2):
    cols = st.columns(2)
    for j, col in enumerate(cols):
        if i + j < len(ad_metrics):
            title, value = ad_metrics[i + j]
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-title">{title}</div>
                        <div class="metric-value">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )