FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système si nécessaire
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]