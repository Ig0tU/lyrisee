FROM python:3.10-slim

# Install system dependencies, including ffmpeg for audio processing
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy requirements and install
COPY --chown=user backend/requirements.txt $HOME/app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download en_core_web_sm

# Copy the backend application
COPY --chown=user backend/ $HOME/app/backend/

# Switch to backend directory so scripts find their local imports
WORKDIR $HOME/app/backend

# Expose port for HuggingFace (7860 is standard for Gradio/FastAPI on Spaces)
EXPOSE 7860

# Command to run the FastAPI app via Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
