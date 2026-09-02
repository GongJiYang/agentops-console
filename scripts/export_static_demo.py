from __future__ import annotations

import http.cookiejar
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:18765"
TOKEN = "agentops-demo"
OUTPUT = Path(__file__).resolve().parents[1] / "_site" / "index.html"

BANNER = """
<div class="demo-banner" role="status">
  Interactive portfolio demo · seeded, non-production data · review decisions stay in this browser
  <a href="https://github.com/GongJiYang/agentops-console">View source</a>
</div>
"""

STATIC_STYLE = """
<style>
.demo-banner{position:sticky;top:0;z-index:20;padding:9px 20px;text-align:center;background:#172238;color:#eef3ff;font-size:12px;font-weight:600;letter-spacing:.01em}
.demo-banner a{color:#a9c1ff;margin-left:10px;text-decoration:underline;text-underline-offset:3px}
.demo-toast{position:fixed;right:18px;bottom:18px;z-index:2000;max-width:360px;padding:12px 15px;border-radius:8px;background:#172238;color:#fff;box-shadow:0 14px 40px rgba(15,23,42,.28);font-size:13px}
.review-card.is-resolved{opacity:0;transform:translateY(-5px);transition:opacity .18s ease,transform .18s ease}
</style>
"""

STATIC_SCRIPT = """
<script>
(() => {
  const showToast = (message) => {
    document.querySelector('.demo-toast')?.remove();
    const toast = document.createElement('div');
    toast.className = 'demo-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 2800);
  };

  const refreshReviewCount = () => {
    const count = document.querySelectorAll('.review-card').length;
    const card = [...document.querySelectorAll('.stat-card')]
      .find((item) => item.querySelector('.label')?.textContent.trim() === 'Needs Review');
    if (card) card.querySelector('.value').textContent = String(count);
    const pill = [...document.querySelectorAll('.risk-pill')]
      .find((item) => /open/i.test(item.textContent));
    if (pill) pill.textContent = `${count} open`;
    const list = document.querySelector('.review-list');
    if (list && count === 0) list.innerHTML = '<div class="empty-review">Review queue clear. All seeded calls have an operator decision.</div>';
  };

  document.querySelectorAll('.review-actions').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const decision = event.submitter?.value === 'escalated' ? 'Escalated' : 'Acknowledged';
      const card = form.closest('.review-card');
      const tool = card?.querySelector('.review-title .mono')?.textContent.trim() || 'tool call';
      card?.classList.add('is-resolved');
      window.setTimeout(() => {
        card?.remove();
        refreshReviewCount();
      }, 180);
      showToast(`${decision} ${tool}. Static demo state updated locally.`);
    });
  });

  document.querySelectorAll('a[href^="/dash"]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      showToast('This static demo keeps navigation local. Run the repository for full audit and admin routes.');
    });
  });
})();
</script>
"""


def wait_until_ready(timeout: float = 25.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/dash/login", timeout=1):
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("AgentOps demo server did not become ready")


def fetch_dashboard() -> str:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    payload = urllib.parse.urlencode({"api_key": TOKEN}).encode()
    request = urllib.request.Request(f"{BASE_URL}/dash/login", data=payload, method="POST")
    with opener.open(request, timeout=10) as response:
        html = response.read().decode("utf-8")
    if "Operations overview" not in html:
        raise RuntimeError("AgentOps dashboard export did not authenticate")
    return html


def make_static(html: str) -> str:
    html = html.replace("</head>", f"{STATIC_STYLE}</head>", 1)
    html = re.sub(r"<body([^>]*)>", lambda match: f"<body{match.group(1)}>{BANNER}", html, count=1)
    html = html.replace("</body>", f"{STATIC_SCRIPT}</body>", 1)
    return html


def main() -> None:
    env = os.environ.copy()
    env.update(
        {
            "MCP_AUTH_TOKEN": TOKEN,
            "AGENTOPS_DEMO": "true",
            "GATEWAY_DB_PATH": "/tmp/agentops-pages.db",
            "GATEWAY_DB": "/tmp/agentops-pages.db",
            "OAUTH_STATE_PATH": "/tmp/agentops-pages-oauth.json",
            "MCP_PORT": "18765",
            "MCP_BASE_URL": BASE_URL,
        }
    )
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_until_ready()
        html = make_static(fetch_dashboard())
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(html, encoding="utf-8")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    print(f"Exported {OUTPUT}")


if __name__ == "__main__":
    main()
