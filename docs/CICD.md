# Phase 6 — CI/CD Pipeline

Automated **test → build → deploy** using GitHub Actions.

---

## Pipeline overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  git push   │────►│  CI workflow │────►│  Tests (pytest) │
│  or PR      │     │  ci.yml      │     │  21 tests       │
└─────────────┘     └──────┬───────┘     └────────┬────────┘
                           │                      │
                           ▼                      ▼
                    ┌──────────────┐     ┌─────────────────┐
                    │ Docker build │     │  All passed ✅  │
                    │ verification │     └─────────────────┘
                    └──────────────┘

┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ push main   │────►│ Deploy wf    │────►│  rsync → EC2    │
│ or manual   │     │ deploy.yml   │     │  docker up      │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │ Health check    │
                                          │ :8001–8003      │
                                          └─────────────────┘
```

**Lead time:** commit → test → deploy in ~3–5 minutes.

---

## Workflows

| File | Trigger | What it does |
|------|---------|--------------|
| `.github/workflows/ci.yml` | Push/PR to `main` | Run pytest + build Docker images |
| `.github/workflows/deploy.yml` | Push to `main` or manual | Test → deploy to EC2 → health check |

---

## Step 1 — Push repo to GitHub

```bash
cd ~/Projects/Lostify
git add .
git commit -m "Add Lostify MVP with CI/CD"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/Lostify.git
git push -u origin main
```

---

## Step 2 — Configure GitHub Secrets

Go to **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value | Example |
|--------|-------|---------|
| `EC2_HOST` | EC2 public IP or DNS | `54.123.45.67` |
| `EC2_USER` | SSH username | `ubuntu` |
| `EC2_SSH_KEY` | Full contents of `.pem` file | `-----BEGIN RSA PRIVATE KEY-----...` |

To copy your key:
```bash
cat ~/Downloads/lostify-key.pem | pbcopy   # macOS
```

---

## Step 3 — Configure GitHub Environment (optional)

1. **Settings → Environments → New environment**
2. Name: `production`
3. Optional: add required reviewers for deploy approval

The deploy workflow uses `environment: production`.

---

## Step 4 — Run CI manually

CI runs automatically on every push/PR. To verify:

1. Push any commit to `main`
2. Open **Actions** tab in GitHub
3. Click **CI** workflow run
4. Confirm both jobs pass:
   - ✅ Run tests (21 tests)
   - ✅ Build Docker images

---

## Step 5 — Deploy to EC2

### Automatic (push to main)

Any push to `main` (excluding docs-only changes) triggers deploy after tests pass.

### Manual trigger

1. **Actions → Deploy to EC2 → Run workflow**
2. Select branch `main`
3. Click **Run workflow**

### What deploy does

1. Runs pytest (pre-deploy gate)
2. `rsync` project files to `~/Lostify/` on EC2
3. Runs `aws/ec2/deploy.sh` (docker compose up --build)
4. Runs health check on all 3 services
5. Posts deployment summary with URLs

---

## Step 6 — Verify deployment

After deploy workflow completes:

```bash
curl http://YOUR_EC2_IP:8001/health
curl http://YOUR_EC2_IP:8002/health
curl http://YOUR_EC2_IP:8003/health
```

Or check the **Summary** tab in the GitHub Actions run.

---

## Run CI locally (same as GitHub Actions)

```bash
chmod +x scripts/ci-local.sh
./scripts/ci-local.sh
```

---

## Pipeline stages detail

### Stage 1 — Test (~30 seconds)

```bash
pip install -r tests/requirements.txt
PYTHONPATH="$(pwd):$(pwd)/item-service:$(pwd)/notification-service" pytest tests/ -v
```

Covers:
- Event serialization (6 event types)
- Duplicate event deduplication
- Saga pattern (approve + reject paths)

### Stage 2 — Build (~2 minutes)

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml config --quiet
```

Validates all 3 service Dockerfiles compile successfully.

### Stage 3 — Deploy (~1–2 minutes)

```bash
rsync → EC2:~/Lostify/
ssh EC2 "bash aws/ec2/deploy.sh"
ssh EC2 "bash aws/ec2/health-check.sh localhost"
```

---

## Disable auto-deploy

To run tests/build on push but deploy only manually, edit `.github/workflows/deploy.yml`:

```yaml
on:
  workflow_dispatch:   # keep manual only
  # push:              # comment out auto-deploy
  #   branches: [main]
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Permission denied (publickey)` | Check `EC2_SSH_KEY` secret — must include full PEM including headers |
| `Host key verification failed` | Re-run deploy; workflow uses `ssh-keyscan` |
| Tests pass locally, fail in CI | Ensure `tests/requirements.txt` includes all deps |
| Docker build OOM on EC2 | Use `t3.small`; add swap if needed |
| Deploy succeeds, health fails | SSH to EC2: `docker compose -f docker-compose.prod.yml logs` |

---

## Security notes

- Never commit `.pem` files or `.env` with real secrets
- Rotate `JWT_SECRET_KEY` in EC2 `.env` after first deploy
- Restrict EC2 security group to your IP for non-demo use
- Use GitHub Environment protection rules for production deploys

---

## Next: Phase 7

Add integration tests, fault tolerance tests, and event latency measurement.
