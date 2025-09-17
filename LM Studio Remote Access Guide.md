# LM Studio Remote Access via Cloudflare Tunnel on MAC

## Quick Reference Guide for Mac (Australia) to Windows PC (Sri Lanka)

---

## Prerequisites Checklist

Before starting, ensure:

- [x] **Mac (Australia)**: LM Studio is installed and running
- [x] **Mac**: GPT OSS 20B model is loaded in LM Studio
- [x] **Mac**: LM Studio server is running (green "Status: Running")
- [x] **Mac**: "Serve on Local Network" is enabled in LM Studio settings
- [x] **Mac**: cloudflared is installed in `~/Desktop/AI/` folder

---

## Step-by-Step Activation Process

### Step 1: Access Mac via Screen Connect
- Connect to your Mac in Australia using Screen Connect
- Open Terminal application

### Step 2: Navigate to AI Folder
```bash
cd ~/Desktop/AI
```

**Verify you're in the right location:**
```bash
pwd
# Should show: /Users/mwdev/Desktop/AI
```

### Step 3: Check cloudflared Installation
```bash
ls -la cloudflared
# Should show executable file with permissions
```

**Test cloudflared version:**
```bash
./cloudflared --version
# Should show: cloudflared version 2025.8.1 (or similar)
```

### Step 4: Start LM Studio Server (if not running)
1. Open LM Studio application
2. Load your GPT OSS 20B model
3. Ensure server is running (green status)
4. Verify "Serve on Local Network" is enabled

### Step 5: Create Cloudflare Tunnel
```bash
./cloudflared tunnel --url http://localhost:1234
```

**Expected output will show:**
```
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://random-words-here.trycloudflare.com                                               |
+--------------------------------------------------------------------------------------------+
```

### Step 6: Copy Your Tunnel URL
**Important:** Copy the exact URL from the output (e.g., `https://random-words-here.trycloudflare.com`)

### Step 7: Test Tunnel on Mac
**Open a NEW terminal window** (keep cloudflared running in the first one):

```bash
curl https://YOUR-TUNNEL-URL.trycloudflare.com/v1/models
```

**Replace `YOUR-TUNNEL-URL` with your actual tunnel URL**

**Expected response:** JSON listing your available models

### Step 8: Update Windows Application (Sri Lanka)
In your Windows PC application configuration, change:

**From:**
```json
"endpoint": "http://127.0.0.1:1234/v1/chat/completions"
```

**To:**
```json
"endpoint": "https://YOUR-TUNNEL-URL.trycloudflare.com/v1/chat/completions"
```

### Step 9: Test from Sri Lanka
On your Windows PC, test the connection:

```cmd
curl https://YOUR-TUNNEL-URL.trycloudflare.com/v1/models
```

**Test chat completion:**
```cmd
curl -X POST https://YOUR-TUNNEL-URL.trycloudflare.com/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"gpt-oss-20b\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello from Sri Lanka!\"}]}"
```

---

## Important Notes

### Keep Tunnel Running
- **Do NOT close** the terminal window running cloudflared
- If closed, tunnel stops immediately
- Your Windows application will lose connection

### URL Changes Every Restart
- Each time you restart cloudflared, you get a **new URL**
- Must update Windows application configuration with new URL
- Previous URLs become invalid

### Security Considerations
- Your LM Studio becomes **publicly accessible** on internet
- Anyone with URL can use your model
- Only run when needed, stop when done

### Stopping the Tunnel
**To stop the tunnel:**
- Press `Ctrl+C` in terminal running cloudflared
- Or close the terminal window
- LM Studio becomes private again

---

## Troubleshooting

### If Tunnel Fails to Start
1. **Check LM Studio is running:**
   ```bash
   curl http://localhost:1234/v1/models
   ```

2. **Verify AI folder location:**
   ```bash
   cd ~/Desktop/AI
   ls -la cloudflared
   ```

3. **Check file permissions:**
   ```bash
   chmod +x cloudflared
   ```

### If Connection Fails from Sri Lanka
1. **Verify tunnel URL is correct**
2. **Test from Mac first** before testing from Sri Lanka
3. **Check for typos** in endpoint configuration
4. **Ensure tunnel terminal is still running**

### Common Error Messages (Normal)
These warnings in cloudflared output are **normal and can be ignored:**
- "Cannot determine default configuration path"
- "Cannot determine default origin certificate path" 
- "cloudflared will not automatically update"

**Success indicators:**
- "Registered tunnel connection"
- "Starting metrics server"
- Public URL displayed in box

---

## Quick Command Reference

### Essential Commands (run from ~/Desktop/AI)
```bash
# Navigate to AI folder
cd ~/Desktop/AI

# Check cloudflared exists
./cloudflared --version

# Create tunnel
./cloudflared tunnel --url http://localhost:1234

# Test tunnel (in new terminal)
curl https://YOUR-URL.trycloudflare.com/v1/models
```

### Emergency Reset
If something goes wrong:
1. **Stop tunnel:** `Ctrl+C`
2. **Restart LM Studio** 
3. **Navigate to AI folder:** `cd ~/Desktop/AI`
4. **Create new tunnel:** `./cloudflared tunnel --url http://localhost:1234`
5. **Update Windows PC** with new URL

---

## Typical Session Workflow

1. **Connect to Mac** via Screen Connect
2. **Open Terminal** → `cd ~/Desktop/AI`
3. **Start tunnel** → `./cloudflared tunnel --url http://localhost:1234`
4. **Copy URL** from output
5. **Update Windows PC** endpoint configuration
6. **Test connection** from both Mac and Sri Lanka
7. **Use your application** with remote LM Studio
8. **Stop tunnel** when done (`Ctrl+C`)

---

**Remember:** Each session requires updating your Windows PC with the new tunnel URL!