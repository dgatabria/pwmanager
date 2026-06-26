FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ./app ./app
COPY ./seed.py .

# Patch slowapi to preserve function signatures for FastAPI compatibility
# slowapi uses functools.wraps but inspect.signature() sees the wrapper's
# (*args, **kwargs) signature. FastAPI uses inspect.signature() to determine
# endpoint parameters. This patch preserves the original signature.
COPY patch_slowapi.py /tmp/patch_slowapi.py
RUN python /tmp/patch_slowapi.py

# Expose port
EXPOSE 8000

# Run migrations then start the application
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
