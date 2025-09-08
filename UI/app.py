import requests
import streamlit as st
import base64
import time
import msal
import os
from dotenv import load_dotenv
import streamlit.components.v1 as components

# Load environment variables from .env file
load_dotenv()

# Azure Entra (Azure AD) Authentication Configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
TENANT_ID = os.getenv('TENANT_ID')
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["User.Read"]  # Only request necessary permissions
API_BASE = "http://127.0.0.1:8000"
REDIRECT_URI = "http://localhost:8501"  # Make sure this matches the registered URI in Azure
logo_path = "tcs_logo.png"

# MSAL Configuration to initiate login
def initiate_login():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    auth_url = app.get_authorization_request_url(SCOPES, redirect_uri=REDIRECT_URI)
    return auth_url

# This function handles the token response after the user authenticates with Azure
def handle_token_response():
    # Get the code from the query parameters in the URL (from the redirect)
    code = st.query_params.get('code')

    if not code:
        st.error("Authorization code not found in URL")
        return None

    # MSAL (Microsoft Authentication Library) to exchange code for token
    app = msal.PublicClientApplication(
        os.getenv('CLIENT_ID'),
        authority=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}"
    )

    # Exchange the authorization code for an access token
    token_response = app.acquire_token_by_authorization_code(
        code,
        scopes=["User.Read"],
        redirect_uri=REDIRECT_URI  # Ensure this matches your registered redirect URI
    )

    if "access_token" in token_response:
        return token_response
    else:
        # st.error("Failed to acquire token")
        return None

# Convert image to base64
def get_image_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

# Streamlit Page Configuration
st.set_page_config(page_title="IAM GENI", page_icon=logo_path, layout="wide")

# Pre-generate the Azure login URL before the button is clicked
auth_url = initiate_login()

# ---------------------- Sidebar ----------------------
st.sidebar.title("Navigation")

# 🔁 AUTH BUTTON TOGGLES: Login → Logout
is_authed = st.session_state.get("authenticated", False)
if is_authed:
    auth_btn = st.sidebar.button("Logout", key="logout_btn")
else:
    auth_btn = st.sidebar.button("Login", key="login_btn")

chat_button = st.sidebar.button("Chat")
about_button = st.sidebar.button("About IAM")
rules_button = st.sidebar.button("Rules and Regulations")

# ---------------------- CSS ----------------------
st.markdown("""
<style>
/* Base layout paddings so footer won't overlap page content */
.block-container { padding-bottom: 90px; }

/* Header row: logo + title side-by-side */
.header-container {
    position: sticky;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0 10px 0;
    border-bottom: 1px solid #e9ecef;
    position: sticky;
    top: 0;
    background: black;
    padding-left: 16px;
    z-index: 1000;
}

/* Control logo size */
.header-container img {
    height: 36px;     /* Adjust logo size here */
    width: auto;
    display: block;
}

/* Title next to logo on same level */
.header-title {
    font-size: 22px;  /* Adjust title size here */
    font-weight: 700;
    line-height: 1;
    margin: 0;
    padding: 0;
}

/* Centered intro text style */
.centered-intro {
    text-align: center;
    font-size: 18px;
    color: #333;
    margin-top: 24px;
}

/* Message container when no messages */
.message-container.no-messages {
    min-height: 30vh;
}

/* Fixed footer at bottom */
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    height: 30px;              /* Footer height */
    background: black;
    border-top: 1px solid white;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 16px;
    z-index: 1001;
    font-size: 12.5px;
    color: rgb(255 255 255);
}

/* Keep Streamlit chat input above the fixed footer */
.stChatFloatingInputContainer {
    bottom: 72px !important;   /* Footer height + small gap */
}

/* Optional: small screen tweaks */
@media (max-width: 600px) {
    .header-title { font-size: 18px; }
    .header-container img { height: 30px; }
    .footer { height: 72px; }
    .stChatFloatingInputContainer { bottom: 80px !important; }
}
</style>
""", unsafe_allow_html=True)

# ---------------------- Header ----------------------
st.markdown(f"""
<div class="header-container">
    <img src="data:image/png;base64,{get_image_base64(logo_path)}" alt="TCS Logo" />
    <p class="header-title">IAM GENI</p>
</div>
""", unsafe_allow_html=True)
st.markdown("""
<style>
.st-emotion-cache-zy6yx3 {
    padding: 2rem 1rem 4rem !important; /* top right/left bottom */
}
</style>
""", unsafe_allow_html=True)

# ---------------------- Footer ----------------------
st.markdown("""
<div class="footer">
    Copyright © 2025 Tata Consultancy Services | Entry to this site is restricted to employees and affiliates.
</div>
""", unsafe_allow_html=True)

# ---------------------- Page Content ----------------------
def show_intro():
    st.markdown('<div class="centered-intro">Ask me anything about Identity and Access Management.</div>', unsafe_allow_html=True)

# ---------------------- Chat Page ----------------------
def main_chat_page():
    if "access_token" not in st.session_state or not st.session_state["access_token"]:
        st.error("Access token is not found or invalid.")
        return

    if "thread_id" not in st.session_state:
        try:
            headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
            r = requests.post(f"{API_BASE}/thread", timeout=60, headers=headers)
            r.raise_for_status()
            st.session_state["thread_id"] = r.json()["thread_id"]
        except Exception as e:
            st.error(f"Failed to create thread: {e}")
            st.stop()

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    container_class = "message-container no-messages" if len(st.session_state["chat_history"]) == 0 else "message-container"
    st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)

    if len(st.session_state["chat_history"]) == 0:
        show_intro()

    container = st.container()
    for user_msg, agent_msg in st.session_state["chat_history"]:
        with container:
            with st.chat_message("user"):
                st.markdown(f"**You:** {user_msg}")
            with st.chat_message("assistant"):
                st.markdown(f"**IAM Assistant:** {agent_msg}")

    st.markdown('</div>', unsafe_allow_html=True)

    prompt = st.chat_input("Say something:")
    if prompt:
        user_input = prompt
        with st.spinner("Thinking..."):
            try:
                headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
                payload = {"thread_id": st.session_state["thread_id"], "message": user_input}
                r = requests.post(f"{API_BASE}/chat", json=payload, timeout=60, headers=headers)
                r.raise_for_status()
                reply = r.json().get("reply", "")
            except Exception as e:
                reply = f"Error: {e}"

        typing_placeholder = st.empty()
        typing_message = ""
        for char in reply:
            typing_message += char
            typing_placeholder.markdown(f"**IAM Assistant**: {typing_message}")
            time.sleep(0.01)

        st.session_state["chat_history"].append((user_input, reply))
        st.rerun()

# ---------------------- About & Rules ----------------------
def about_iam():
    st.write("**About IAM**")
    st.write("Identity and Access Management (IAM) is a framework of policies and technologies that ensure the right individuals have appropriate access to technology resources.")

def rules_and_regulations():
    st.write("**Rules and Regulations**")
    st.write("1. Only authorized users can access the system.")
    st.write("2. Users must follow the company's security guidelines.")
    st.write("3. All actions performed in the system must be logged.")
    st.write("4. MFA must be enabled for sensitive areas.")

# ---------------------- Sidebar Logic ----------------------
# Handle Login click when NOT authenticated
if not is_authed and auth_btn:
    auth_url = initiate_login()
    st.markdown("""**Note**: A pop-up window will open for authentication. Please ensure pop-ups are enabled in your browser.""")
    components.html(f"""
    <script>
        var loginWindow = window.open("{auth_url}", "_blank", "width=800,height=600");
        if (loginWindow) {{
            loginWindow.focus();
        }} else {{
            alert("Pop-up was blocked. Please allow pop-ups in your browser.");
        }}
    </script>
    """, height=0)

# Handle Logout click when authenticated
if is_authed and auth_btn:
    # Clear auth/session
    for k in ["authenticated", "access_token", "thread_id", "chat_history"]:
        st.session_state.pop(k, None)
    # Clear ?code= from URL if present
    try:
        # Streamlit's query_params acts like a MutableMapping
        st.query_params.pop("code", None)
    except Exception:
        pass
    st.sidebar.success("Logged out")
    st.rerun()

# Handle token response after redirect
if "code" in st.query_params:
    token_response = handle_token_response()  # Call the function to handle the response
    if token_response and "access_token" in token_response:
        st.session_state["authenticated"] = True
        st.session_state["access_token"] = token_response.get("access_token")
        st.session_state["auth_url"] = None  # Clear login link
        st.sidebar.success("Successfully logged in")
        st.rerun()

# Main page content based on authentication status
if st.session_state.get("authenticated", False):
    if chat_button:
        main_chat_page()
    elif about_button:
        about_iam()
    elif rules_button:
        rules_and_regulations()
    else:
        main_chat_page()
else:
    st.write("Please log in to access the IAM Assistant.")
