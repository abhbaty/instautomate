import gradio as gr
from main import app as custom_app

# Create a dummy Gradio interface to keep Hugging Face happy
demo = gr.Blocks()
with demo:
    gr.Markdown("# 🤖 InstaAutomate is Running!\n\nAccess your dashboard at [**`/dashboard`**](/dashboard).")

# Mount our FastAPI app. Hugging Face's SDK will detect 'app' and run it using its own Uvicorn.
app = gr.mount_gradio_app(custom_app, demo, path="/gradio_home")

