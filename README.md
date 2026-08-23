# brainspark-daily-sketch-agent
🧠 AI-powered always-on agent that generates daily drawing sketches for kids. Built on AWS Free Tier.

# 🧠✨ BrainSpark — Daily Drawing Sketch Agent for Kids

An **always-on AI agent** that automatically generates unique daily drawing sketches for kids every morning. Built entirely on **AWS Free Tier** with zero cost.

![Architecture](screenshots/architecture.png)

---

## 🎯 What It Does

- 🎨 Generates a **unique coloring page** every morning at 7 AM IST
- 📱 Delivers via **Telegram Bot** with interactive feedback polls
- 🧠 **Learns from feedback** — adapts themes based on user preferences
- 🔄 **Smooth theme transitions** — connected themes, not random jumps
- 🌐 **Public dashboard** showing evolution history on S3

---

## 🏗️ Architecture

| AWS Service | Purpose |
|-------------|---------|
| **AWS Lambda** | Core agent brain — runs sketch generation logic |
| **Amazon EventBridge** | Schedules daily trigger at 7 AM IST |
| **Amazon DynamoDB** | Stores sketch history + user feedback |
| **Amazon S3** | Hosts public dashboard website |
| **AWS IAM** | Manages permissions |

| External Service | Purpose |
|-----------------|---------|
| **Cloudflare Workers AI** | Image generation (Stable Diffusion XL) — 10,000 free/day |
| **Pollinations.ai** | Fallback image generation (unlimited) |
| **Telegram Bot API** | Delivery + feedback collection |

---

## 🔄 How the Smart Feedback Loop Works

