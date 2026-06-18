FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic pydantic-settings httpx openai Pillow ruamel.yaml python-multipart

COPY src/ src/
COPY skills/ skills/

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
