# Dokploy Deployment Guide for Personal RAG

This guide outlines how to host your **Personal RAG** application in **Dokploy**, a modern self-hosted Platform-as-a-Service (PaaS) built on Docker Swarm and Traefik, customized for your domain **`*.quanphungg.me`**.

We have pre-configured production files in the repository:
- [front-end/Dockerfile](file:///home/quan/personal-rag/front-end/Dockerfile) — SPA-optimized Multi-stage production build using Nginx.
- [front-end/nginx.conf](file:///home/quan/personal-rag/front-end/nginx.conf) — Custom configuration with gzip compression and SPA fallback routing.
- [docker-compose.prod.yml](file:///home/quan/personal-rag/docker-compose.prod.yml) — Production-ready multi-container orchestration stripped of development bind mounts.

---

## Strategy 1: Deploy as a Dokploy Compose Stack (Recommended)

This is the easiest and most cohesive approach, as it preserves the exact inter-container networking and dependency ordering defined in your docker-compose config.

### Step 1: Create a Compose Project in Dokploy
1. Log in to your Dokploy Dashboard.
2. Click **Create Project** (or navigate to an existing Project).
3. Under the **Services** section, click **Create Service** and select **Compose**.
4. Give it a name (e.g., `personal-rag-stack`).

### Step 2: Configure the Stack
1. Inside your new Compose service, go to the **Source** tab.
2. Select **Git** and connect your repository:
   - **Repository URL**: Your git repository URL.
   - **Branch**: `main` (or your production branch).
   - **Compose File Path**: `docker-compose.prod.yml`.
3. Save the configurations.

### Step 3: Add Environment Variables
Go to the **Environment** tab of the Compose service and add the following required production environment variables.

| Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `mongodb+srv://user:pass@cluster.mongodb.net/personal-rag` | MongoDB connection string (e.g. Atlas or self-hosted) |
| `MINIO_ROOT_USER` | `minio_admin` (custom name) | MinIO admin dashboard username |
| `MINIO_ROOT_PASSWORD` | *Strong Random String (e.g., 32+ chars)* | MinIO admin dashboard password |
| `JWT_SECRET_KEY` | *Generate secure token (`openssl rand -hex 32`)* | Backend authentication key |
| `RESEND_API_KEY` | *Your Resend API Key* | (Optional) Email sender configuration |
| `RESEND_FROM_EMAIL` | `noreply@quanphungg.me` | Verified sending domain email |
| `OPENROUTER_API_KEY` | *Your OpenRouter API Key* | API key for LLM integrations |
| `CHAT_PROVIDER` | `openrouter` | LLM provider selector (`openrouter` or `gemini`) |
| `GEMINI_API_KEY` | *Your Gemini API Key* | Required when `CHAT_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini chat model override |
| `CORS_ORIGINS` | `["https://rag.quanphungg.me", "https://quanphungg.me"]` | JSON list of allowed origins |
| `VITE_API_URL` | `https://api.quanphungg.me` | Public URL of backend API |
| `S3_PUBLIC_ENDPOINT_URL` | `https://s3.quanphungg.me` | Public URL of MinIO storage endpoint |
| `MINIO_BROWSER_REDIRECT_URL` | `https://s3-console.quanphungg.me` | MinIO browser console redirection URL |
| `MINIO_SERVER_URL` | `https://s3.quanphungg.me` | Public API endpoint for MinIO storage |
| `S3_BUCKET` | `personal-rag-bucket` | S3 bucket name |
| `RABBITMQ_DEFAULT_USER` | `rag_rabbitmq` | RabbitMQ username |
| `RABBITMQ_DEFAULT_PASS` | *Strong Random String (e.g., 32+ chars)* | RabbitMQ password |
| `POLAR_API_KEY` | *Your Polar Organization Access Token* | Enables billing; checkout/portal return 503 without it |
| `POLAR_WEBHOOK_SECRET` | *Webhook secret from the Polar endpoint registered for this domain* | Verifies inbound `POST /api/v1/billing/webhooks/polar` |
| `POLAR_ENVIRONMENT` | `production` | Switches the Polar API base URL from sandbox to production |
| `POLAR_ORGANIZATION_ID` | *Your Polar production Organization ID* | Not read by code today, kept for reference/future validation |
| `POLAR_PLUS_PRODUCT_ID` | *Product ID for the $20/mo Plus plan (fixed recurring price)* | Used by checkout session creation for the "plus" tier |
| `POLAR_PRO_PRODUCT_ID` | *Product ID for the $100/mo Pro plan (fixed recurring price)* | Used by checkout session creation for the "pro" tier |
| `POLAR_LLM_TOKENS_METER_ID` | *Production meter ID* | Tracking/audit only ($0/unit) — not the billing mechanism |
| `POLAR_SUCCESS_URL` | `https://rag.quanphungg.me/settings/billing?checkout=success` | Where Polar redirects after a successful checkout |
| `FREE_TIER_LLM_TOKENS_ALLOWANCE` | `50000` (or desired monthly token limit) | Free-tier LLM token cap before checkout is required |
| `PLUS_TIER_LLM_TOKENS_ALLOWANCE` | `5000000` | Hard token cap for Plus subscribers (blocked once exceeded) |
| `PRO_TIER_LLM_TOKENS_ALLOWANCE` | `35000000` | Hard token cap for Pro subscribers (blocked once exceeded) |

### Step 4: Expose Services via Domains
Dokploy integrates seamlessly with Traefik to handle Let's Encrypt SSL certificates automatically. To expose the Frontend, Backend, and MinIO publicly, go to the **Domains** tab in each respective service configuration or configure it via the Dokploy UI:
- **Frontend Service**: Route public domain `https://rag.quanphungg.me` (or `https://quanphungg.me`) to internal container port `80`.
- **Backend Service**: Route public domain `https://api.quanphungg.me` to internal container port `8000`.
- **MinIO Service**: 
  - Route public domain `https://s3-console.quanphungg.me` to internal container port `9001` (console UI).
  - Route public domain `https://s3.quanphungg.me` to internal container port `9000` (API endpoint).

### Step 5: Deploy
Click **Deploy** in the top-right corner. Dokploy will pull the code, build the backend and frontend Dockerfiles in production mode, set up the volumes, boot the services, and auto-provision your SSL certificates.

---

## Strategy 2: Deploy as Individual Services (For Advanced Control)

If you want to manage backups, scale services, and monitor resource metrics separately, you can split them into individual native Dokploy services.

### 1. Database (MongoDB)
1. In Dokploy, click **Create Service** and select **Database** -> **MongoDB** (or use a cloud-managed service like MongoDB Atlas).
2. If self-hosting via Dokploy Database: Dokploy will auto-generate your connection details. Save them. Note that Atlas Vector Search features are only available in Atlas, but standard querying and indexing work in standard MongoDB.

### 2. MinIO (Object Storage)
1. Click **Create Service** -> **Application**.
2. In the **Source** tab, select **Docker Image**.
3. Set the image to `minio/minio:latest`.
4. Under **General/Command**, set the command to `server /data --console-address ":9001"`.
5. Set up a persistent volume mount `/data` -> `minio-data-volume`.
7. Add environment variables for admin access:
   - `MINIO_ROOT_USER`: *Your Root User*
   - `MINIO_ROOT_PASSWORD`: *Your Root Password*
8. Bind two domains:
   - API domain: `https://s3.quanphungg.me` -> Port `9000`.
   - Console domain: `https://s3-console.quanphungg.me` -> Port `9001`.

### 3. Backend (FastAPI Application)
1. Click **Create Service** -> **Application**.
2. Select your git repository, branch `main`, and set the subfolder path to `back-end`.
3. In the **Build** tab, select **Dockerfile** (Dokploy will automatically find the Dockerfile in `back-end/Dockerfile`).
4. Set the **Environment Variables** in the UI (including the database URL generated in Step 1, MinIO credentials, keys, etc.).
5. Bind a domain: `https://api.quanphungg.me` -> Port `8000`.
6. Enable automatic deployments under the **Triggers** tab so that git commits to your branch auto-update the API!

### 4. Frontend (Vite SPA Application)
1. Click **Create Service** -> **Application**.
2. Select your git repository, branch `main`, and set the subfolder path to `front-end`.
3. In the **Build** tab, you have two options:
   - **Nixpacks**: Dokploy native builder. It will auto-detect Vite and build it automatically.
   - **Dockerfile**: Use the newly created `front-end/Dockerfile`. Set the build argument `VITE_API_URL` to `https://api.quanphungg.me`.
4. Bind a domain: `https://rag.quanphungg.me` (or `https://quanphungg.me`) -> Port `80` (since Nginx serves it on port 80).
5. Enable automatic deployments under the **Triggers** tab.

### 5. RabbitMQ + MinIO Event Setup (Required for Document Uploads)
Because MinIO and Backend are standalone, you must ensure MinIO publishes `ObjectCreated` events to RabbitMQ and that the backend can consume that queue.

> [!TIP]
> Provision a RabbitMQ service in the same Dokploy project first, then set the backend `RABBITMQ_*` environment variables so the app can consume the durable queue.

If you choose to configure the AMQP notification manually via the `mc` CLI:
1. Access your Dokploy server via SSH or run a temporary helper container in the network.
2. Authenticate the CLI with MinIO:
   ```bash
   mc alias set local https://s3.quanphungg.me your_minio_root_user your_minio_root_password
   ```
3. Create the bucket:
   ```bash
   mc mb --ignore-existing local/personal-rag-bucket
   ```
4. Register the AMQP target and bucket notification (requires restarting the MinIO service after the config change):
   ```bash
   mc admin config set local notify_amqp:backend \
     url="amqp://your_rabbitmq_user:your_rabbitmq_password@rabbitmq:5672" \
     exchange="minio-events" \
     exchange_type="direct" \
     routing_key="minio.object.created" \
     durable="on"
   mc admin service restart local
   mc event add local/personal-rag-bucket arn:minio:sqs::backend:amqp --event put
   ```

---

## Important Security Checkpoints

> [!WARNING]
> **Production CORS Configuration**
> Ensure your `CORS_ORIGINS` environment variable matches the exact domain on which your frontend is hosted. For example:
> `CORS_ORIGINS=["https://rag.quanphungg.me", "https://quanphungg.me"]`

> [!IMPORTANT]
> **Cookie Security**
> In production, change the following backend environment variables to protect user session cookies:
> - `COOKIE_SECURE=true` (forces HTTPS cookies)
> - `COOKIE_SAMESITE=lax` (prevents CSRF attacks while maintaining user sessions)

> [!TIP]
> **Data Persistence**
> Verify that the Dokploy volumes (such as `mongodb_data` and `minio_prod_data` in Compose, or native volumes under individual applications) are persistent. Avoid using ephemeral server directories to ensure your users' notebooks, files, and logins survive server restarts or container builds.
