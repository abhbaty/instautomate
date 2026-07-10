import gradio as gr
import spaces
from main import app as custom_app

# Dummy function to satisfy HF ZeroGPU runtime
@spaces.GPU
def dummy_gpu():
    pass

# Create a dummy Gradio interface to keep Hugging Face happy
demo = gr.Blocks()
with demo:
    gr.Markdown("# 🤖 InstaAutomate is Running!\n\nAccess your dashboard at [**`/dashboard`**](/dashboard).")
    # Bind the GPU function to an event so HF detects it
    btn = gr.Button("Wake GPU", visible=False)
    btn.click(fn=dummy_gpu, inputs=[], outputs=[])

# Mount our FastAPI app. Hugging Face's SDK will detect 'app' and run it using its own Uvicorn.
app = gr.mount_gradio_app(custom_app, demo, path="/gradio_home")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
