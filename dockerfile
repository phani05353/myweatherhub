FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything, including the templates folder
COPY . .

# Ensure the templates folder exists in the container (Safety Check)
RUN ls -R /app/templates

EXPOSE 5000

CMD ["python", "app.py"]