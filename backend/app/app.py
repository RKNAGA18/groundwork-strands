import os
import shutil
import gradio as gr
from app.storage.chunker import chunk_document
from app.storage.vector_store import VectorStoreManager
from app.agent.strands_pipeline import set_vector_store, run_pipeline

# 1. Securely fetch API Key from Render environment
api_key = os.environ.get("GROQ_API_KEY")
if api_key:
    os.environ["GROQ_API_KEY"] = api_key

# 2. Initialize In-Memory Vector Store
KB_ID = "eval_kb"
vsm = VectorStoreManager()
vsm.create_kb(KB_ID)
set_vector_store(vsm, KB_ID)

# 3. Define UI Functions
def upload_and_index(file_obj):
    if file_obj is None:
        return "Please upload a file."
    
    # Save uploaded file
    os.makedirs('eval/synthetic_kb', exist_ok=True)
    filename = os.path.basename(file_obj.name)
    dest_path = os.path.join('eval/synthetic_kb', filename)
    shutil.copy(file_obj.name, dest_path)
    
    # Chunk and index directly into the Vector Store
    chunks = chunk_document(dest_path)
    vsm.add_chunks(KB_ID, chunks)
    return f"Successfully uploaded and indexed: {filename}"

def run_ui_query(question):
    if not question:
        return "Please enter a compliance question."
    
    # Execute your existing Strands SDK pipeline
    result = run_pipeline(question)
    
    status = result.get("status", "RED")
    reason = result.get("reason", "No specific reason provided.")
    source = result.get("top_source", "None")
    
    # Format the UI Badges exactly like the video
    if status.upper() == "GREEN":
        badge = "🟢 STATUS: GREEN (Supported by Policy)"
    else:
        badge = "🔴 STATUS: RED (Policy Gap / Hallucination Caught)"
        
    return f"{badge}\n\nAuditor Verdict: {reason}\nCitation: {source}"

# 4. Build the Dashboard Interface
with gr.Blocks(theme=gr.themes.Monochrome()) as demo:
    gr.Markdown("# Groundwork: Multi-Agent Compliance Verifier")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 1. Knowledge Base Ingestion")
            file_in = gr.File(label="Upload Security Policy (.md)")
            upload_btn = gr.Button("Ingest Document")
            upload_status = gr.Textbox(label="System Status", interactive=False)
            
        with gr.Column():
            gr.Markdown("### 2. Live Agentic Audit")
            query_in = gr.Textbox(label="Enter Compliance Question")
            query_btn = gr.Button("Run Live Verifier", variant="primary")
            audit_out = gr.Textbox(label="Verifier Agent Output", lines=6, interactive=False)
            
    # Connect buttons to functions
    upload_btn.click(upload_and_index, inputs=file_in, outputs=upload_status)
    query_btn.click(run_ui_query, inputs=query_in, outputs=audit_out)

# 5. Render Deployment Launch Command
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    demo.launch(server_name="0.0.0.0", server_port=port)
