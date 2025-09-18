
import streamlit as st
from iamagent import IAMAssistant
from iam_observability import observability_queue

st.set_page_config(page_title="IAM Assistant", layout="wide")

# Initialize agent once
if "agent" not in st.session_state:
    st.session_state.agent = IAMAssistant()

# Chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Observability toggle
if "show_observability" not in st.session_state:
    st.session_state.show_observability = True

st.title("🔐 IAM Assistant")

# ------------------------
# CSS for chat bubbles
# ------------------------
st.markdown(
    """
    <style>
    .user-bubble {
        background-color: #ffffff;
        color: #000000;
        padding: 10px 15px;
        border-radius: 15px;
        max-width: 70%;
        margin-bottom: 5px;
        display: inline-block;
        border: 1px solid #ddd;
    }
    .assistant-bubble {
        background-color: #ff4d4d;
        color: white;
        padding: 10px 15px;
        border-radius: 15px;
        max-width: 70%;
        margin-bottom: 5px;
        display: inline-block;
    }
    .chat-row {
        display: flex;
        align-items: flex-start;
        margin-bottom: 10px;
    }
    .chat-row.user {
        justify-content: flex-start;
    }
    .chat-row.assistant {
        justify-content: flex-end;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------
# Display chat history
# ------------------------
for chat in st.session_state.chat_history:
    # User bubble
    st.markdown(
        f"""
        <div class="chat-row user">
            <div class="user-bubble">{chat['user']}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Assistant bubble
    st.markdown(
        f"""
        <div class="chat-row assistant">
            <div class="assistant-bubble">{chat['agent']}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Observability
    if st.session_state.show_observability:
        if chat.get("logs"):
            with st.expander("📜 Live Observability", expanded=False):
                st.text("\n".join(chat["logs"]))
        if chat.get("trace"):
            with st.expander("🧭 Trace Summary", expanded=False):
                st.markdown(chat["trace"])

    st.markdown("---")

# ------------------------
# Input form
# ------------------------
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("💬 Ask your question:")
    cols = st.columns([4, 2])
    with cols[0]:
        submit_button = st.form_submit_button("Send")
    with cols[1]:
        st.session_state.show_observability = st.checkbox(
            "🔎 Show Observability", value=st.session_state.show_observability
        )

# ------------------------
# Handle new query
# ------------------------
if submit_button and user_input:
    live_logs = []
    trace_summary_text = ""
    final_response = ""

    # Create a live container for streaming logs
    live_obs_box = st.empty()
    trace_box = st.empty()
    response_box = st.empty()

    for step in st.session_state.agent.search_iam_docs_stream(user_input):
        # Drain live observability events
        while not observability_queue.empty():
            event = observability_queue.get()
            log_msg = f"- {event['operation']}"
            if event.get("detail"):
                log_msg += f": {event['detail']}"
            live_logs.append(log_msg)
            if st.session_state.show_observability:
                live_obs_box.text("\n".join(live_logs))
            observability_queue.task_done()

        # When agent response is ready
        if step.get("operation") == "Response Ready":
            final_response = step["response"]

            # Display agent response
            response_box.markdown(
                f"""
                <div class="chat-row assistant">
                    <div class="assistant-bubble">{final_response}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Display Trace Summary separately (from step, not queue)
            if st.session_state.show_observability and "trace_data" in step:
                td = step["trace_data"]
                trace_summary_text = (
                    f"**Intent:** {td['intent']}\n\n"
                    f"**System:** {td['system']}\n\n"
                    f"**Agent:** {td['agent']}\n\n"
                    f"**Operation:** {td['operation']}"
                )
                trace_box.markdown(f"🧭 Trace Summary\n\n{trace_summary_text}")

    # Save turn
    st.session_state.chat_history.append({
        "user": user_input,
        "agent": final_response,
        "logs": live_logs if st.session_state.show_observability else None,
        "trace": trace_summary_text if st.session_state.show_observability else None
    })

    st.rerun()
