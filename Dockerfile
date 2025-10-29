# AIS Ship Movement Simulator - Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install pymongo dependency
RUN pip install --no-cache-dir pymongo

# Copy simulator script
COPY ship_simulator.py .

# Set environment variable for MongoDB URI (can be overridden at runtime)
ENV MONGODB_URI=""

# Run the simulator
# Use unbuffered output so logs appear immediately in docker logs
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "ship_simulator.py"]
CMD []
