import spaces  # Must use HF's pre-installed version - NOT from pip
import gradio as gr
from main import app as custom_app

@spaces.GPU
def gpu_startup():
    """Dummy GPU function — satisfies HF ZeroGPU requirement."""
    return "ready"

with gr.Blocks() as demo:
    gr.Markdown(
        "# 🤖 InstaAutomate is Running!\n\n"
        "Your automation tool is live. Open your "
        "[**Dashboard →**](/dashboard) to manage campaigns."
    )
    # Bind GPU function to page load so HF detects it at startup
    hidden_out = gr.Textbox(visible=False)
    demo.load(fn=gpu_startup, inputs=None, outputs=hidden_out)

# Mount our FastAPI app into the Gradio server
app = gr.mount_gradio_app(custom_app, demo, path="/gradio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
