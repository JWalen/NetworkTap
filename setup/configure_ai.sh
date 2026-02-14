#!/bin/bash
# Configure AI features for NetworkTap
# Installs Ollama and downloads the recommended model
set -e

source /etc/networktap.conf

echo "[+] Configuring AI features..."

# ── Install Ollama ──────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "[+] Installing Ollama..."
    
    # Ollama install script (official)
    curl -fsSL https://ollama.com/install.sh | sh
    
    if command -v ollama &>/dev/null; then
        echo "[+] Ollama installed successfully"
    else
        echo "[!] Ollama installation failed. AI Assistant will not be available."
        echo "[!] You can install manually: https://ollama.com/download"
    fi
else
    echo "[i] Ollama already installed: $(ollama --version 2>/dev/null || echo 'unknown')"
fi

# ── Enable and start Ollama service ─────────────────────────────────
if systemctl list-unit-files | grep -q ollama; then
    echo "[+] Enabling Ollama service..."
    systemctl enable ollama
    systemctl start ollama
    
    # Wait for Ollama to be ready
    echo "[+] Waiting for Ollama to start..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags &>/dev/null; then
            echo "[+] Ollama is running"
            break
        fi
        sleep 1
    done
fi

# ── Pull the recommended model ──────────────────────────────────────
if [[ "${AI_ASSISTANT_ENABLED:-yes}" == "yes" ]] && command -v ollama &>/dev/null; then
    MODEL="${OLLAMA_MODEL:-tinyllama}"
    
    echo "[+] Checking for model: ${MODEL}"
    
    # Check if model exists
    if ! ollama list 2>/dev/null | grep -q "${MODEL}"; then
        echo "[+] Downloading model '${MODEL}'..."
        echo "[i] This may take several minutes depending on your internet connection..."
        
        ollama pull "${MODEL}" || {
            echo "[!] Failed to download model. You can do this later with:"
            echo "    ollama pull ${MODEL}"
        }
    else
        echo "[i] Model '${MODEL}' already available"
    fi
    
    # List available models
    echo "[+] Available Ollama models:"
    ollama list 2>/dev/null || true
fi

# ── Verify AI features ──────────────────────────────────────────────
echo ""
echo "[+] AI Feature Status:"
echo "    Anomaly Detection: ${ANOMALY_DETECTION_ENABLED:-yes}"
echo "    AI Assistant: ${AI_ASSISTANT_ENABLED:-yes}"
echo "    Ollama URL: ${OLLAMA_URL:-http://localhost:11434}"
echo "    Model: ${OLLAMA_MODEL:-tinyllama}"

if command -v ollama &>/dev/null && curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "    Ollama Status: Running ✓"
else
    echo "    Ollama Status: Not running (AI Assistant unavailable)"
fi

echo ""
echo "[+] AI configuration complete"
echo "[i] You can manage AI settings in the web UI under Settings > AI Features"
