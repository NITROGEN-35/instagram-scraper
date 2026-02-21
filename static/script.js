// ── Helpers ────────────────────────────────────────────────────────────────

function show(id)  { document.getElementById(id).classList.remove("hidden"); }
function hide(id)  { document.getElementById(id).classList.add("hidden"); }
function setText(id, val) { document.getElementById(id).textContent = val; }

function setStatus(msg) {
    show("statusBar");
    setText("statusMsg", msg);
}

function fmt(val) {
    if (!val || val === "Not found" || val === "Not extracted") return "—";
    const n = parseInt(String(val).replace(/,/g, ""), 10);
    if (isNaN(n)) return val;
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000)     return (n / 1_000).toFixed(1) + "K";
    return n.toLocaleString();
}

// ── Scrape ──────────────────────────────────────────────────────────────────

async function scrapeReel() {
    const urlInput = document.getElementById("reelUrl");
    const url = urlInput.value.trim();

    if (!url) {
        urlInput.focus();
        return;
    }
    if (!url.includes("instagram.com")) {
        showError("That doesn't look like an Instagram URL. Please paste a reel link.");
        return;
    }

    // ── UI: loading state ──
    const btn = document.getElementById("scrapeBtn");
    btn.disabled = true;
    hide("btnText");
    show("btnSpinner");
    hide("resultCard");
    hide("errorCard");
    setStatus("Launching Chrome with your profile...");

    // Animate status messages to keep user informed (scraping takes a few seconds)
    const statusMessages = [
        "Launching Chrome with your profile...",
        "Navigating to Instagram...",
        "Waiting for page to load...",
        "Extracting reel data...",
        "Almost done...",
    ];
    let msgIdx = 0;
    const statusTimer = setInterval(() => {
        msgIdx = Math.min(msgIdx + 1, statusMessages.length - 1);
        setStatus(statusMessages[msgIdx]);
    }, 3000);

    try {
        const response = await fetch("/scrape", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });

        const data = await response.json();

        clearInterval(statusTimer);
        hide("statusBar");

        if (data.error) {
            showError(data.error);
        } else {
            showResult(data);
            await loadHistory();
        }

    } catch (err) {
        clearInterval(statusTimer);
        hide("statusBar");
        showError("Network error: " + err.message);
    } finally {
        btn.disabled = false;
        show("btnText");
        hide("btnSpinner");
    }
}

function showResult(data) {
    setText("resViews",    fmt(data.views));
    setText("resLikes",    fmt(data.likes));
    setText("resComments", fmt(data.comments));
    setText("resCaption",  data.caption !== "Not found" ? data.caption : "No caption found.");
    show("resultCard");
}

function showError(msg) {
    setText("errorMsg", msg);
    show("errorCard");
}

// ── History table ───────────────────────────────────────────────────────────

async function loadHistory() {
    try {
        const response = await fetch("/data");
        const rows = await response.json();

        const tbody = document.getElementById("tableBody");
        const count = document.getElementById("rowCount");

        count.textContent = `${rows.length} record${rows.length !== 1 ? "s" : ""}`;

        if (rows.length === 0) {
            tbody.innerHTML = `<tr class="empty-row"><td colspan="6">No data yet — scrape a reel above.</td></tr>`;
            return;
        }

        tbody.innerHTML = rows.map((row, i) => {
            const shortUrl = row.URL ? row.URL.replace("https://www.instagram.com/", "ig.com/") : "—";
            return `
            <tr>
                <td style="color:var(--muted); width:40px">${i + 1}</td>
                <td class="caption-cell">${escape(row.Caption)}</td>
                <td class="num">${fmt(row.Views)}</td>
                <td class="num">${fmt(row.Likes)}</td>
                <td class="num">${fmt(row.Comments)}</td>
                <td class="url-cell">
                    ${row.URL
                        ? `<a href="${row.URL}" target="_blank" rel="noopener" title="${row.URL}">${shortUrl}</a>`
                        : "—"}
                </td>
            </tr>`;
        }).join("");

    } catch (err) {
        console.error("Failed to load history:", err);
    }
}

function escape(str) {
    if (!str) return "—";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ── Enter key support ────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("reelUrl").addEventListener("keydown", (e) => {
        if (e.key === "Enter") scrapeReel();
    });
    loadHistory();
});