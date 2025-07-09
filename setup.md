## 📄 **Docker & Compose Startup Setup on Boot**

---

### ✅ **1. Install Docker Engine & Compose**

```bash
# Install yum utils
sudo yum install -y yum-utils

# Add Docker repo
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Install Docker Engine + CLI + Compose plugin
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

### ✅ **2. Enable and Start Docker Service**

```bash
# Enable Docker on boot
sudo systemctl enable docker

# Start Docker now
sudo systemctl start docker

# Verify installation
docker version
```

---

### ✅ **3. Add Your User to Docker Group (optional)**

```bash
# Add your user to docker group (replace $USER if needed)
sudo usermod -aG docker $USER

# Log out and log back in to apply group change
```

---

### ✅ **4. Test Docker Compose**

```bash
# Go to your project folder
cd /path/to/your/compose/project

# Run Docker Compose up
docker compose up -d
```

---

### ✅ **5. Run Compose Automatically on Boot**

Create a **systemd unit** to run your Compose project at boot.

```bash
sudo nano /etc/systemd/system/myapp.service
```

Paste this (update `/path/to/your/compose/project`!):

```ini
[Unit]
Description=My Docker Compose App
After=network.target docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/your/compose/project
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Save and close.

---

### ✅ **6. Enable and Start the Service**

```bash
# Reload systemd to pick up the new unit
sudo systemctl daemon-reload

# Enable the service to run at boot
sudo systemctl enable myapp.service

# Start it now
sudo systemctl start myapp.service

# Check status
sudo systemctl status myapp.service
```

---

### ✅ **Done!**

Your **Docker Compose app** will now:

* Start on boot.
* Stop when the service is stopped.
* Run in the background (`-d`).

---

**✅ Tip:**
If your Compose file is in a Git repo, you might want to pull latest before `up` — adjust `ExecStart` like:

```ini
ExecStart=/usr/bin/git pull && /usr/bin/docker compose up -d
```

---

Save this as `startup_instructions.txt` or `README.md`.

If you’d like, I can write you a ready‑to‑copy file — just say **`yes`**!
