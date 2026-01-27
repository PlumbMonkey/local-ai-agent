"""Gradio Web GUI for Local AI Agent.

A modern chat interface with:
- Real-time streaming responses
- Model selection
- Conversation history
- System prompt customization
"""

import gradio as gr
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from core.llm.ollama import OllamaClient


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI coding assistant running locally via Ollama.
You help with programming questions, code review, debugging, and general software development.
Be concise but thorough. Use code blocks with syntax highlighting when showing code."""


# ═══════════════════════════════════════════════════════════════════════════════
# Ollama Client
# ═══════════════════════════════════════════════════════════════════════════════

client = OllamaClient()

# Current settings (can be changed via UI)
current_model = DEFAULT_MODEL
current_system_prompt = DEFAULT_SYSTEM_PROMPT


def get_available_models():
    """Get list of available Ollama models."""
    try:
        models = client.list_models()
        return models if models else [DEFAULT_MODEL]
    except Exception:
        return [DEFAULT_MODEL]


def check_ollama_status():
    """Check if Ollama is running."""
    try:
        return client.health_check()
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Chat Function
# ═══════════════════════════════════════════════════════════════════════════════

def respond(message: str, history: list):
    """
    Process a chat message and return the response.
    
    Args:
        message: User's input message
        history: List of {"role": "user/assistant", "content": "..."} dicts
    
    Returns:
        Response text
    """
    global current_model, current_system_prompt
    
    if not message.strip():
        return ""
    
    # Build the full prompt with context
    parts = []
    
    # Add system prompt
    if current_system_prompt:
        parts.append(f"System: {current_system_prompt}\n")
    
    # Add conversation history (last 10 exchanges)
    for msg in history[-20:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            parts.append(f"User: {content}")
        else:
            parts.append(f"Assistant: {content}")
    
    # Add current message
    parts.append(f"User: {message}")
    parts.append("Assistant:")
    
    full_prompt = "\n\n".join(parts)
    
    try:
        response = client.generate(current_model, full_prompt)
        return response
    except Exception as e:
        return f"❌ Error: {str(e)}\n\nMake sure Ollama is running: `ollama serve`"


def update_model(model: str):
    """Update the current model."""
    global current_model
    current_model = model
    return f"✅ Model set to: {model}"


def update_system_prompt(prompt: str):
    """Update the system prompt."""
    global current_system_prompt
    current_system_prompt = prompt
    return "✅ System prompt updated"


# ═══════════════════════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════════════════════

def create_ui():
    """Create the Gradio interface."""
    
    # Check Ollama status
    ollama_running = check_ollama_status()
    models = get_available_models() if ollama_running else [DEFAULT_MODEL]
    
    with gr.Blocks(title="Local AI Agent") as app:
        
        # Header
        gr.Markdown(
            """
            # 🤖 Local AI Agent
            ### Privacy-first AI assistant running entirely on your machine
            """
        )
        
        # Status bar
        if ollama_running:
            gr.Markdown(f"✅ **Ollama Connected** | Models: {', '.join(models)}")
        else:
            gr.Markdown("❌ **Ollama Not Running** | Start with: `ollama serve`")
        
        # Settings accordion
        with gr.Accordion("⚙️ Settings", open=False):
            with gr.Row():
                model_dropdown = gr.Dropdown(
                    choices=models,
                    value=models[0] if models else DEFAULT_MODEL,
                    label="Model",
                    interactive=True,
                    scale=2,
                )
                model_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    scale=3,
                )
            
            system_prompt_box = gr.Textbox(
                value=DEFAULT_SYSTEM_PROMPT,
                label="System Prompt",
                lines=3,
                placeholder="Instructions for the AI assistant...",
            )
            with gr.Row():
                save_prompt_btn = gr.Button("💾 Save System Prompt", size="sm")
                prompt_status = gr.Textbox(
                    label="",
                    interactive=False,
                    show_label=False,
                    scale=3,
                )
            
            # Wire settings events
            model_dropdown.change(update_model, inputs=model_dropdown, outputs=model_status)
            save_prompt_btn.click(update_system_prompt, inputs=system_prompt_box, outputs=prompt_status)
        
        # Main chat interface
        gr.ChatInterface(
            fn=respond,
            examples=[
                "Write a Python function to reverse a string",
                "Explain async/await in Python",
                "What's the difference between a list and a tuple?",
                "Help me debug: TypeError: 'NoneType' object is not subscriptable",
            ],
        )
        
        # Footer
        gr.Markdown(
            """
            ---
            <center>
            💻 Running locally via Ollama | 🔒 Your data stays on your machine
            </center>
            """,
        )
    
    return app


# ═══════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Launch the GUI."""
    print("🚀 Starting Local AI Agent GUI...")
    print("=" * 50)
    
    # Check Ollama
    if check_ollama_status():
        print("✅ Ollama is running")
        print(f"📦 Available models: {', '.join(get_available_models())}")
    else:
        print("⚠️  Ollama not detected. Start it with: ollama serve")
    
    print("=" * 50)
    print("🌐 Opening browser at http://127.0.0.1:7860")
    print("   Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Create and launch app
    app = create_ui()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        show_error=True,
    )


if __name__ == "__main__":
    main()
