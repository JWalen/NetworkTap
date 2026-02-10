"""AI Assistant integration using Ollama for network analysis.

Provides natural language interface for:
- Summarizing alerts and traffic patterns
- Answering questions about network activity
- Explaining security events
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional

import httpx

from core.config import get_config

logger = logging.getLogger("networktap.ai")


# System prompt for the network security assistant
SYSTEM_PROMPT = """You are a network security analyst assistant for NetworkTap, a network monitoring appliance.
You help analyze network traffic, explain security alerts, and identify potential threats.

When analyzing data:
- Be concise and actionable
- Highlight security concerns first
- Use technical terms but explain them briefly
- Suggest next steps when appropriate

Available data types you may receive:
- Suricata IDS alerts (intrusion detection)
- Zeek connection logs (network metadata)
- DNS query logs
- Traffic statistics

Keep responses brief (2-3 paragraphs max) unless asked for detailed analysis."""


class AIAssistant:
    """Ollama-based AI assistant for network analysis."""

    def __init__(self, config=None):
        self.config = config or get_config()
        self._available: Optional[bool] = None
        self._model_loaded = False

    @property
    def enabled(self) -> bool:
        return self.config.ai_assistant_enabled

    @property
    def ollama_url(self) -> str:
        return self.config.ollama_url

    @property
    def model(self) -> str:
        return self.config.ollama_model

    async def check_availability(self) -> dict:
        """Check if Ollama is running and the model is available."""
        if not self.enabled:
            return {"available": False, "reason": "AI Assistant is disabled in config"}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check Ollama is running
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code != 200:
                    return {"available": False, "reason": "Ollama not responding"}

                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]

                # Check if our model is available
                model_base = self.model.split(":")[0]
                model_available = any(model_base in m for m in models)

                if model_available:
                    self._available = True
                    return {
                        "available": True,
                        "model": self.model,
                        "models": models,
                    }
                else:
                    return {
                        "available": False,
                        "reason": f"Model '{self.model}' not found. Available: {models}",
                        "models": models,
                    }

        except httpx.ConnectError:
            return {"available": False, "reason": "Cannot connect to Ollama. Is it running?"}
        except Exception as e:
            return {"available": False, "reason": str(e)}

    async def chat(self, message: str, context: Optional[dict] = None) -> str:
        """Send a message and get a response."""
        if not self.enabled:
            return "AI Assistant is disabled. Enable it in Settings."

        # Build the prompt with context
        prompt = self._build_prompt(message, context)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": SYSTEM_PROMPT,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 500,  # Limit response length
                        }
                    }
                )

                if resp.status_code != 200:
                    return f"Error: Ollama returned status {resp.status_code}"

                data = resp.json()
                return data.get("response", "No response generated")

        except httpx.ConnectError:
            return "Error: Cannot connect to Ollama. Make sure it's running with `systemctl start ollama`"
        except httpx.TimeoutException:
            return "Error: Request timed out. The model may be loading or the query is too complex."
        except Exception as e:
            logger.error("AI chat error: %s", e)
            return f"Error: {str(e)}"

    async def chat_stream(self, message: str, context: Optional[dict] = None) -> AsyncGenerator[str, None]:
        """Stream a response token by token."""
        if not self.enabled:
            yield "AI Assistant is disabled. Enable it in Settings."
            return

        prompt = self._build_prompt(message, context)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": SYSTEM_PROMPT,
                        "stream": True,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 500,
                        }
                    }
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    yield data["response"]
                                if data.get("done"):
                                    break
                            except json.JSONDecodeError:
                                continue

        except httpx.ConnectError:
            yield "Error: Cannot connect to Ollama."
        except Exception as e:
            yield f"Error: {str(e)}"

    def _build_prompt(self, message: str, context: Optional[dict] = None) -> str:
        """Build the full prompt with context data."""
        parts = []

        if context:
            parts.append("=== Current Network Context ===")

            if "alerts" in context:
                parts.append(f"\nRecent Alerts ({len(context['alerts'])} total):")
                for alert in context["alerts"][:10]:
                    parts.append(f"- [{alert.get('severity', '?')}] {alert.get('title', 'Unknown')}: {alert.get('description', '')[:100]}")

            if "stats" in context:
                stats = context["stats"]
                parts.append(f"\nTraffic Stats (last hour):")
                parts.append(f"- Connections: {stats.get('total_connections', 0):,}")
                parts.append(f"- Data transferred: {stats.get('total_bytes', 0):,} bytes")
                parts.append(f"- Unique source IPs: {stats.get('unique_src_ips', 0)}")
                parts.append(f"- Unique dest IPs: {stats.get('unique_dest_ips', 0)}")

            if "top_talkers" in context:
                parts.append(f"\nTop Talkers:")
                for t in context["top_talkers"][:5]:
                    parts.append(f"- {t.get('ip', '?')}: {t.get('bytes', 0):,} bytes")

            if "anomalies" in context:
                parts.append(f"\nDetected Anomalies ({len(context['anomalies'])} total):")
                for a in context["anomalies"][:5]:
                    parts.append(f"- {a.get('title', 'Unknown')}: {a.get('description', '')[:80]}")

            parts.append("\n=== End Context ===\n")

        parts.append(f"User Question: {message}")
        return "\n".join(parts)

    async def summarize_alerts(self, hours: int = 24) -> str:
        """Generate a summary of recent alerts."""
        from core.alert_parser import parse_suricata_alerts
        from core.anomaly_detector import get_detector

        config = get_config()
        alerts = parse_suricata_alerts(config.suricata_eve_log, limit=50)
        anomalies = get_detector().get_recent_anomalies(20)

        context = {
            "alerts": alerts,
            "anomalies": anomalies,
        }

        return await self.chat(
            "Summarize the security alerts and anomalies. What are the main concerns and what should I investigate?",
            context
        )

    async def analyze_ip(self, ip: str) -> str:
        """Analyze activity for a specific IP address."""
        from core.zeek_parser import get_log_entries

        # Get connections involving this IP
        conns = get_log_entries("conn", page=1, per_page=100, filters={"ip": ip})

        context = {
            "connections": [
                {
                    "dest": c.get("id.resp_h"),
                    "port": c.get("id.resp_p"),
                    "service": c.get("service"),
                    "bytes": (c.get("orig_bytes", 0) or 0) + (c.get("resp_bytes", 0) or 0),
                }
                for c in conns.entries[:20]
            ]
        }

        return await self.chat(
            f"Analyze the network activity for IP {ip}. What services is it connecting to? Any concerns?",
            context
        )

    async def explain_alert(self, alert: dict) -> str:
        """Explain a specific alert in plain language."""
        return await self.chat(
            f"Explain this security alert in plain language and suggest what action to take:\n"
            f"Alert: {alert.get('title', 'Unknown')}\n"
            f"Description: {alert.get('description', 'No description')}\n"
            f"Source: {alert.get('source_ip', 'Unknown')} -> {alert.get('dest_ip', 'Unknown')}:{alert.get('dest_port', '')}\n"
            f"Severity: {alert.get('severity', 'Unknown')}"
        )


# Global assistant instance
_assistant: Optional[AIAssistant] = None


def get_assistant() -> AIAssistant:
    """Get or create the global AI assistant."""
    global _assistant
    if _assistant is None:
        _assistant = AIAssistant()
    return _assistant
