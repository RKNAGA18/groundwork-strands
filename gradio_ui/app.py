import gradio as gr
import requests
import os

# This points to your live backend!
API_URL = "https://groundwork-dashboard.onrender.com"

def upload_doc(file):
    if file is None:
        return "Please upload a document."
    try:
        files = {"file": open(file.name, "rb")}
        res = requests.post(f"{API_URL}/api/kb/upload", files=files)
        
        if res.status_code == 200:
            return "✅ Knowledge Base successfully uploaded and indexed into memory."
        return f"Upload failed: {res.text}"
    except Exception as e:
        return f"Error connecting to backend: {str(e)}"

def verify(question):
    if not question:
        return "Please enter a compliance question."
    try:
        res = requests.post(f"{API_URL}/api/verify-single", json={"question": question})
        
        if res.status_code == 200:
            data = res.json()
            status = data.get("status", "red").upper()
            
            badge = "🟢 STATUS: GREEN (Supported by Policy)" if status == "GREEN" else "🔴 STATUS: RED (Policy Gap Caught)"
            reason = data.get("reason", "No reason provided.")
            source = data.get("source_doc", "No citation available.")
            
            return f"{badge}\n\nAuditor Verdict: {reason}\nCitation: {source}"
        
        return f"Verification failed: {res.text}"
    except Exception as e:
        return f"Error connecting to backend: {str(e)}"

with gr.Blocks(theme=gr.themes.Monochrome()) as demo:
    gr.Markdown("# Groundwork: Multi-Agent Compliance Verifier")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 1. Ingest Knowledge Base")
            file_in = gr.File(label="Upload Security Policy (.md / .pdf)")
            upload_btn = gr.Button("Ingest Document")
            upload_out = gr.Textbox(label="System Status", interactive=False)
            
            upload_btn.click(upload_doc, inputs=file_in, outputs=upload_out)
            
        with gr.Column():
            gr.Markdown("### 2. Live Agentic Audit")
            query_in = gr.Textbox(label="Enter Compliance Claim")
            verify_btn = gr.Button("Run Verifier Agent", variant="primary")
            verify_out = gr.Textbox(label="Verifier Output", lines=6, interactive=False)
            
            verify_btn.click(verify, inputs=query_in, outputs=verify_out)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    demo.launch(server_name="0.0.0.0", server_port=port)
