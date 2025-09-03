import streamlit as st
from backend import ask_gemini

st.set_page_config(page_title="GCP Assistant", page_icon="☁️", layout="wide")


st.title("☁️ GCP Assistant")
st.write("Ask questions in natural language, and I’ll convert them into GCP CLI commands and give results.")

# Input
question = st.text_input("Enter your question:")

if st.button("Ask"):
    if question.strip():
        with st.spinner("Processing..."):
            command, mcp_result, answer = ask_gemini(question)

        # st.subheader("🔹 Generated gcloud Command")
        # st.code(command, language="bash")
    
        # st.subheader("📦 Raw MCP Result")
        # st.json(mcp_result)

        st.subheader("✅ Final Answer")
        st.write(answer)
    else:
        st.warning("Please enter a valid question.")
