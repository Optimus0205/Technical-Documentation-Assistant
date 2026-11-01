# Deploying FastAPI with Docker

## Dockerfile

Create a file named `Dockerfile` next to your app. It describes how to build the container image:

```dockerfile
FROM python:3.12-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app /code/app
CMD ["fastapi", "run", "app/main.py", "--port", "80"]
```

## Build and run

Build the image with `docker build -t myapp .` and start a container with `docker run -p 80:80 myapp`.
The application is then available on port 80 of your machine.