# PoliticsEye — Production Deployment

<p>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/AWS_EC2-FF9900?style=flat&logo=amazonaws&logoColor=white"/>
  <img src="https://img.shields.io/badge/Nginx-009639?style=flat&logo=nginx&logoColor=white"/>
  <img src="https://img.shields.io/badge/MongoDB-47A248?style=flat&logo=mongodb&logoColor=white"/>
  <img src="https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white"/>
  <img src="https://img.shields.io/badge/Let's_Encrypt-003A70?style=flat&logo=letsencrypt&logoColor=white"/>
  <img src="https://img.shields.io/badge/Ubuntu-E95420?style=flat&logo=ubuntu&logoColor=white"/>
</p>

> Production deployment of [PoliticsEye](https://github.com/areebmohd/PoliticsEye) — a Real-Time Political Sentiment Tracker. This repository documents the complete infrastructure setup, containerisation, database migration, and deployment automation on AWS.

**Application developed by:** [@areebmohd](https://github.com/areebmohd)  
**Deployment & Infrastructure by:** [@aman-mishra-05](https://github.com/aman-mishra-05)  
**Live at:** https://politicseye.run.place  
**Contact:** amanmishraproff@gmail.com

![PoliticsEye Live](https://raw.githubusercontent.com/aman-mishra-05/PoliticsEye_deployment/main/assets/screenshot.png)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Docker Configuration](#docker-configuration)
- [AWS Infrastructure](#aws-infrastructure)
- [Database Migration](#database-migration)
- [SSL and HTTPS](#ssl-and-https)
- [Auto-start on Reboot](#auto-start-on-reboot)
- [Automated Backups](#automated-backups)
- [Deployment Guide](#deployment-guide)
- [Operations Reference](#operations-reference)

---

## Overview

This deployment covers the full production infrastructure for PoliticsEye. The application stack — a Flask backend, React frontend, and MongoDB database — is fully containerised using Docker and orchestrated with Docker Compose on a single AWS EC2 instance.

### Scope of Work

| Area | Details |
|---|---|
| Containerisation | Dockerfiles for backend, frontend (multi-stage build), and MongoDB |
| Orchestration | Docker Compose with two isolated bridge networks |
| Infrastructure | AWS EC2 provisioning, EBS persistent storage, Elastic IP |
| Database | MongoDB containerised; 51,782 documents migrated from Atlas |
| Web Server | Nginx reverse proxy with React SPA routing and HTTPS |
| SSL/HTTPS | Let's Encrypt certificates via Certbot with auto-renewal |
| Reliability | systemd service for auto-start, daily automated backups |
| Domain | Custom domain configured via DNS A record |

---

## Architecture

```
                        ┌──────────────────────────────────┐
         HTTPS          │      EC2 t3.small (Ubuntu 22.04)  │
User ──────────────────▶│                                   │
  politicseye.run.place │  ┌─────────────────────────────┐  │
                        │  │   Docker Compose Networks    │  │
                        │  │                             │  │
                        │  │  ┌───────────────────────┐  │  │
                        │  │  │    nginx container    │  │  │
                        │  │  │    Port 80 / 443      │  │  │
                        │  │  │  · Serves React build │  │  │
                        │  │  │  · Proxies /api/*     │  │  │
                        │  │  └──────────┬────────────┘  │  │
                        │  │             │  frontend_net  │  │
                        │  │  ┌──────────▼────────────┐  │  │
                        │  │  │   backend container   │  │  │
                        │  │  │  Flask + Gunicorn      │  │  │
                        │  │  │  · 2 workers           │  │  │
                        │  │  │  · Scraper thread      │  │  │
                        │  │  └──────────┬────────────┘  │  │
                        │  │             │  backend_net   │  │
                        │  │  ┌──────────▼────────────┐  │  │
                        │  │  │    mongo container    │  │  │
                        │  │  │    MongoDB 7          │  │  │
                        │  │  │    Internal only      │  │  │
                        │  │  └──────────┬────────────┘  │  │
                        │  └─────────────┼───────────────┘  │
                        │                │                   │
                        │  ┌─────────────▼─────────────────┐│
                        │  │  Named Volume: mongo_data      ││
                        │  │  Backed by EBS 30GB gp3        ││
                        │  └───────────────────────────────┘│
                        └──────────────────────────────────┘
```

### Network Isolation

Two separate Docker bridge networks enforce a strict traffic path:

```
Internet → nginx (frontend_net) → backend (backend_net) → mongo
```

The `mongo` container is completely isolated — unreachable from the internet and unreachable directly from the `nginx` container. All database traffic must pass through `backend`.

---

## Repository Structure

```
PoliticsEye/
├── backend/
│   ├── Dockerfile              ← Added for deployment
│   └── ...                     (application source — original)
├── frontend/
│   ├── Dockerfile              ← Added for deployment
│   ├── nginx.conf              ← Added for deployment
│   └── ...                     (application source — original)
├── mongo-init/
│   └── mongod.conf             ← Added for deployment
├── docker-compose.yml          ← Added for deployment
├── .env.example                ← Added for deployment
└── .gitignore
```

All application source code is original work by [@areebmohd](https://github.com/areebmohd). Files marked above were created as part of this deployment.

---

## Docker Configuration

### `backend/Dockerfile`

```dockerfile
FROM python:3.11.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import nltk; nltk.download('stopwords'); \
               nltk.download('vader_lexicon'); nltk.download('punkt')"

COPY . .
EXPOSE 5000
CMD ["gunicorn", "app:app", "--workers", "2", "--bind", "0.0.0.0:5000", "--timeout", "120"]
```

Two Gunicorn workers provide sufficient concurrency for a t3.small without memory exhaustion. The `--timeout 120` flag prevents worker timeouts caused by TensorFlow's cold-start latency on first request.

---

### `frontend/Dockerfile` — Multi-stage Build

```dockerfile
# Stage 1 — Build React
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN VITE_API_BASE_URL=/api npm run build

# Stage 2 — Serve with Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

The two-stage build ensures no Node.js runtime or build tooling exists in the production image — only compiled static assets are carried forward. Setting `VITE_API_BASE_URL=/api` at build time makes all API calls use relative paths, allowing Nginx to proxy them correctly regardless of host IP or domain.

---

### `frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name politicseye.run.place www.politicseye.run.place;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name politicseye.run.place www.politicseye.run.place;

    ssl_certificate /etc/letsencrypt/live/politicseye.run.place/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/politicseye.run.place/privkey.pem;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

`try_files $uri $uri/ /index.html` is required for React Router — without it, direct URL access or page refresh returns a 404. The `backend` hostname resolves automatically via Docker's internal DNS.

---

### `mongo-init/mongod.conf` — Memory Tuning

```yaml
storage:
  wiredTiger:
    engineConfig:
      cacheSizeGB: 0.25
```

By default, MongoDB's WiredTiger storage engine allocates 50% of available RAM as cache — on a 2GB t3.small this would consume 1GB, leaving insufficient memory for the Flask and Nginx containers. Capping the cache at 256MB keeps the full stack within a stable memory envelope.

---

### `docker-compose.yml`

```yaml
services:
  mongo:
    image: mongo:7
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
      - ./mongo-init/mongod.conf:/etc/mongod.conf:ro
    command: ["mongod", "--config", "/etc/mongod.conf"]
    expose:
      - "27017"
    mem_limit: 512m
    networks:
      - backend_net

  backend:
    build: ./backend
    restart: unless-stopped
    env_file: .env
    expose:
      - "5000"
    depends_on:
      - mongo
    networks:
      - backend_net
      - frontend_net

  frontend:
    build: ./frontend
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend
    networks:
      - frontend_net

networks:
  frontend_net:
    driver: bridge
  backend_net:
    driver: bridge

volumes:
  mongo_data:
```

---

## AWS Infrastructure

| Component | Specification |
|---|---|
| Instance Type | EC2 t3.small (2 vCPU, 2GB RAM) |
| Operating System | Ubuntu Server 22.04 LTS |
| Storage | EBS 30GB gp3 — delete-on-termination disabled |
| Public IP | Elastic IP (static across reboots) |
| Security Group | Inbound: 80/TCP, 443/TCP (public) · 22/TCP (restricted) |
| Domain | `politicseye.run.place` via FreeDomain.one |

### Instance Sizing

| Service | Memory Usage |
|---|---|
| MongoDB (WiredTiger capped) | ~300 MB |
| Flask + Gunicorn + TensorFlow (2 workers) | ~400 MB |
| Nginx | ~20 MB |
| Ubuntu OS overhead | ~200 MB |
| **Total** | **~920 MB** |

A t3.small (2GB) provides approximately 1GB of headroom. A t3.micro (1GB) is insufficient for this stack due to TensorFlow's in-process memory requirements.

---

## Database Migration

The original application used MongoDB Atlas. The entire database was migrated to the self-hosted containerised MongoDB using a direct streaming pipe — no intermediate files, no data written to disk during transfer.

```bash
# Step 1 — Start only the mongo container
docker-compose up -d mongo

# Step 2 — Stream dump from Atlas directly into the running container
mongodump \
  --uri="mongodb+srv://<user>:<pass>@cluster.mongodb.net/politics_eye" \
  --archive \
| docker-compose exec -T mongo mongorestore \
  --archive \
  --nsFrom="politics_eye.*" \
  --nsTo="politics_eye.*"

# Step 3 — Verify document count
docker-compose exec mongo mongosh politics_eye \
  --eval "db.posts.countDocuments()"
```

**Migration result:** 51,782 documents successfully transferred.

Post-migration, `MONGO_URI` points to the container address:
```
MONGO_URI=mongodb://mongo:27017/politics_eye
```

`mongo` resolves to the container IP via Docker's internal DNS. No Atlas dependency remains after migration.

---

## SSL and HTTPS

SSL certificates are issued by **Let's Encrypt** via **Certbot** in standalone mode. Standalone mode is required because Nginx runs inside Docker, not on the host — the Certbot Nginx plugin cannot reach it directly.

```bash
sudo certbot certonly --standalone \
  -d politicseye.run.place \
  -d www.politicseye.run.place \
  --email amanmishraproff@gmail.com \
  --agree-tos \
  --non-interactive
```

The certificate directory is mounted into the Nginx container as a read-only volume:
```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
```

All HTTP traffic is permanently redirected to HTTPS via a 301 in `nginx.conf`.

### Certificate Auto-renewal

Let's Encrypt certificates expire every 90 days. A cron job handles renewal automatically:

```bash
0 3 * * * certbot renew \
  --pre-hook "cd /home/ubuntu/PoliticsEye && docker-compose stop frontend" \
  --post-hook "cd /home/ubuntu/PoliticsEye && docker-compose start frontend"
```

The pre-hook stops the Nginx container to free port 80 for ACME domain verification. The post-hook restarts it immediately after renewal completes.

---

## Auto-start on Reboot

A **systemd service** ensures all containers restart automatically following any EC2 reboot or unexpected shutdown.

```ini
# /etc/systemd/system/politicseye.service
[Unit]
Description=PoliticsEye Docker Compose Application
After=docker.service
Requires=docker.service

[Service]
WorkingDirectory=/home/ubuntu/PoliticsEye
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable politicseye
sudo systemctl start politicseye
```

---

## Automated Backups

Daily backups of the `politics_eye` database are written to the host filesystem and retained for 7 days. Backups older than 7 days are purged automatically to prevent disk exhaustion.

```bash
# Crontab entry — runs daily at 2am
0 2 * * * cd /home/ubuntu/PoliticsEye && \
  docker-compose exec -T mongo mongodump \
  --db politics_eye --archive --gzip \
  > /home/ubuntu/backups/backup_$(date +\%Y\%m\%d).gz && \
  find /home/ubuntu/backups -name "*.gz" -mtime +7 -delete
```

### Manual Restore

```bash
docker-compose exec -T mongo mongorestore \
  --db politics_eye \
  --drop \
  --archive --gzip \
  < ~/backups/backup_YYYYMMDD.gz
```

---

## Deployment Guide

### Prerequisites

- AWS EC2 t3.small, Ubuntu 22.04, 30GB EBS (delete-on-termination disabled)
- Security Group: inbound 22, 80, 443
- Elastic IP associated with instance

```bash
# Install Docker on EC2
sudo apt update && sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu && newgrp docker
```

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/areebmohd/PoliticsEye.git
cd PoliticsEye

# 2. Configure environment variables
cp .env.example .env
nano .env

# 3. Start MongoDB first
docker-compose up -d mongo

# 4. Migrate existing data (first deployment only)
mongodump --uri="<atlas_connection_string>" --archive \
| docker-compose exec -T mongo mongorestore --archive \
  --nsFrom="politics_eye.*" --nsTo="politics_eye.*"

# 5. Build and start the full stack
docker-compose up -d --build

# 6. Verify all containers are running
docker-compose ps
```

### Environment Variables

```env
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=PoliticalSentimentBot/1.0
NEWS_API_KEY=
MONGO_URI=mongodb://mongo:27017/politics_eye
```

---

## Operations Reference

```bash
# Stream all container logs
docker-compose logs -f

# Stream logs for a specific service
docker-compose logs -f backend

# Restart a single container
docker-compose restart backend

# Deploy after a code update
git pull && docker-compose up -d --build

# Open MongoDB shell
docker-compose exec mongo mongosh politics_eye

# Monitor container memory and CPU usage
docker stats

# Create a manual database backup
docker-compose exec -T mongo mongodump \
  --db politics_eye --archive --gzip \
  > ~/backups/manual_$(date +%Y%m%d).gz

# Check SSL certificate expiry
sudo certbot certificates

# Check systemd service status
sudo systemctl status politicseye
```

---

## Deployment Checklist

| Item | Status |
|---|---|
| Application containerised (backend, frontend, MongoDB) | ✅ |
| Docker Compose with two isolated bridge networks | ✅ |
| 51,782 documents migrated from MongoDB Atlas | ✅ |
| AWS EC2 t3.small provisioned with 30GB EBS | ✅ |
| Elastic IP configured (static public address) | ✅ |
| Custom domain (`politicseye.run.place`) configured | ✅ |
| HTTPS via Let's Encrypt (Certbot standalone) | ✅ |
| HTTP → HTTPS permanent redirect | ✅ |
| SSL certificate auto-renewal via cron | ✅ |
| Auto-start on EC2 reboot via systemd | ✅ |
| Daily automated MongoDB backups (7-day retention) | ✅ |

---

## Deployment Stack

| Tool | Version | Role |
|---|---|---|
| Docker | 24+ | Containerisation |
| Docker Compose | 1.29 | Container orchestration |
| Nginx | Alpine | Reverse proxy, static file server, SSL termination |
| Gunicorn | 21+ | WSGI server for Flask |
| MongoDB | 7 | Database |
| AWS EC2 | t3.small | Cloud compute |
| AWS EBS | gp3 30GB | Persistent volume storage |
| Let's Encrypt | — | SSL certificate authority |
| Certbot | — | Certificate provisioning and renewal |
| systemd | — | Process supervision and auto-start |
| Ubuntu | 22.04 LTS | Host operating system |
