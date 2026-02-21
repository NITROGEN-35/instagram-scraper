import json
import time
import re
import os
import shutil
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# =======================================================================
#  CONFIG — set these two values to match your Chrome installation
# =======================================================================
#
#  HOW TO FIND YOUR PATH:
#    Open Chrome → go to chrome://version → look at "Profile Path"
#    Copy everything UP TO (not including) the last folder name.
#
#  Windows : r"C:\Users\YourName\AppData\Local\Google\Chrome\User Data"
#  Mac     : "/Users/YourName/Library/Application Support/Google/Chrome"
#  Linux   : "/home/yourname/.config/google-chrome"
#
#  PROFILE NAME = the last folder shown in chrome://version
#  Usually "Default", sometimes "Profile 1", "Profile 2", etc.

REAL_PROFILE_PATH = r"C:\Users\abhij\AppData\Local\Google\Chrome\User Data"
REAL_PROFILE_NAME = "Default"

# =======================================================================


def _copy_cookies_to_temp(real_path, profile_name):
    """
    Copy session files from the real Chrome profile into a fresh temp dir.
    This gives Selenium a logged-in Instagram session WITHOUT locking the
    real profile Chrome is already using (the 'directory already in use' fix).
    """
    temp_dir = tempfile.mkdtemp(prefix="ig_selenium_")
    dest_profile = os.path.join(temp_dir, "Default")
    os.makedirs(dest_profile, exist_ok=True)

    src_profile = os.path.join(real_path, profile_name)
    for fname in ["Cookies", "Login Data", "Web Data", "Preferences"]:
        src = os.path.join(src_profile, fname)
        dst = os.path.join(dest_profile, fname)
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
                print(f"[Scraper] Copied {fname}")
            except Exception as e:
                print(f"[Scraper] Could not copy {fname}: {e}")

    return temp_dir


def _build_driver():
    temp_profile = _copy_cookies_to_temp(REAL_PROFILE_PATH, REAL_PROFILE_NAME)

    options = Options()
    options.add_argument(f"--user-data-dir={temp_profile}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # Do NOT use headless — Instagram detects and blocks it

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )
    driver._temp_profile_dir = temp_profile
    return driver


# ── Extraction strategies ────────────────────────────────────────────────────

def _extract_from_ld_json(driver):
    """Strategy 1: Structured ld+json VideoObject metadata."""
    caption, views = "Not found", "Not found"
    try:
        scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        for script in scripts:
            try:
                data = json.loads(script.get_attribute("innerHTML"))
                if isinstance(data, list):
                    data = next((d for d in data if d.get("@type") == "VideoObject"), {})
                if data.get("@type") == "VideoObject":
                    caption = data.get("description", "Not found")
                    stats = data.get("interactionStatistic", [])
                    if isinstance(stats, list) and stats:
                        views = str(stats[0].get("userInteractionCount", "Not found"))
                    elif isinstance(stats, dict):
                        views = str(stats.get("userInteractionCount", "Not found"))
                    break
            except (json.JSONDecodeError, IndexError):
                continue
    except Exception:
        pass
    return caption, views


def _extract_from_page_json(driver):
    """
    Strategy 2: Scan ALL inline <script> tags for any JSON blob that contains
    reel metrics. Instagram embeds data in various keys depending on version.
    """
    caption, likes, views, comments = "Not found", "Not found", "Not found", "Not found"
    try:
        scripts = driver.find_elements(By.TAG_NAME, "script")
        for script in scripts:
            try:
                raw = script.get_attribute("innerHTML") or ""
                if not raw or len(raw) < 50:
                    continue

                # ── Views ──
                for pattern in [
                    r'"video_view_count"\s*:\s*(\d+)',
                    r'"play_count"\s*:\s*(\d+)',
                    r'"video_play_count"\s*:\s*(\d+)',
                    r'"ig_play_count"\s*:\s*(\d+)',
                    r'"view_count"\s*:\s*(\d+)',
                ]:
                    m = re.search(pattern, raw)
                    if m:
                        views = m.group(1)
                        break

                # ── Likes ──
                for pattern in [
                    r'"like_count"\s*:\s*(\d+)',
                    r'"edge_media_preview_like"\s*:\s*\{"count"\s*:\s*(\d+)',
                    r'"likes"\s*:\s*\{"count"\s*:\s*(\d+)',
                    r'"fb_like_count"\s*:\s*(\d+)',
                ]:
                    m = re.search(pattern, raw)
                    if m:
                        likes = m.group(1)
                        break

                # ── Comments ──
                for pattern in [
                    r'"comment_count"\s*:\s*(\d+)',
                    r'"edge_media_to_comment"\s*:\s*\{"count"\s*:\s*(\d+)',
                    r'"comments_count"\s*:\s*(\d+)',
                ]:
                    m = re.search(pattern, raw)
                    if m:
                        comments = m.group(1)
                        break

                # ── Caption ──
                for pattern in [
                    r'"caption"\s*:\s*\{"edges"\s*:\s*\[.*?"text"\s*:\s*"(.*?)"',
                    r'"accessibility_caption"\s*:\s*"(.*?)"',
                    r'"caption"\s*:\s*"((?:[^"\\]|\\.)*)"',
                ]:
                    m = re.search(pattern, raw, re.DOTALL)
                    if m and m.group(1).strip():
                        caption = m.group(1)
                        break

                # Stop once we have at least views or likes
                if views != "Not found" or likes != "Not found":
                    break

            except Exception:
                continue
    except Exception:
        pass
    return caption, likes, views, comments


def _extract_from_graphql(driver):
    """
    Strategy 3: Try fetching Instagram's internal GraphQL endpoint for the post.
    Works only when the user is logged in.
    """
    caption, likes, views, comments = "Not found", "Not found", "Not found", "Not found"
    try:
        # Extract the shortcode from the current URL
        m = re.search(r'/reel/([A-Za-z0-9_-]+)', driver.current_url)
        if not m:
            return caption, likes, views, comments
        shortcode = m.group(1)

        # Use JS fetch so it inherits the browser's cookies (logged-in session)
        js = f"""
        const resp = await fetch(
            'https://www.instagram.com/api/v1/media/shortcode/{shortcode}/',
            {{headers: {{'X-IG-App-ID': '936619743392459'}}}}
        );
        return await resp.text();
        """
        raw = driver.execute_async_script(
            "var cb = arguments[arguments.length-1];"
            f"fetch('https://www.instagram.com/api/v1/media/shortcode/{shortcode}/',"
            "  {headers: {'X-IG-App-ID': '936619743392459'}})"
            ".then(r => r.text()).then(cb).catch(() => cb(''));"
        )
        if raw:
            data = json.loads(raw)
            media = data.get("items", [{}])[0]

            views    = str(media.get("play_count",    media.get("view_count",    "Not found")))
            likes    = str(media.get("like_count",    "Not found"))
            comments = str(media.get("comment_count", "Not found"))
            cap_obj  = media.get("caption", {})
            if isinstance(cap_obj, dict):
                caption = cap_obj.get("text", "Not found")
            elif isinstance(cap_obj, str):
                caption = cap_obj

    except Exception as e:
        print(f"[Scraper] GraphQL strategy failed: {e}")

    return caption, likes, views, comments


def _extract_from_dom(driver):
    """Strategy 4: Last resort — visible DOM elements and aria-labels."""
    caption, likes, views, comments = "Not found", "Not found", "Not found", "Not found"

    # Caption
    for sel in [
        "//h1",
        "//span[contains(@class,'_aade')]",
        "//div[contains(@class,'_a9zs')]//span",
        "//div[@role='dialog']//span[string-length(text()) > 10]",
        "//article//span[string-length(text()) > 10]",
    ]:
        try:
            el = driver.find_element(By.XPATH, sel)
            text = el.text.strip()
            if text and len(text) > 3:
                caption = text
                break
        except Exception:
            continue

    # Views via aria-label (e.g. "1,234 plays")
    for sel in [
        "//*[contains(@aria-label,'plays')]",
        "//*[contains(@aria-label,'views')]",
        "//span[contains(text(),'plays')]",
        "//span[contains(text(),'views')]",
    ]:
        try:
            el = driver.find_element(By.XPATH, sel)
            text = el.get_attribute("aria-label") or el.text
            nums = re.findall(r'[\d,]+', text)
            if nums:
                views = nums[0].replace(",", "")
                break
        except Exception:
            continue

    # Likes via aria-label (e.g. "5,678 likes")
    for sel in [
        "//*[contains(@aria-label,'likes')]",
        "//*[contains(@aria-label,'like')]",
    ]:
        try:
            el = driver.find_element(By.XPATH, sel)
            text = el.get_attribute("aria-label") or el.text
            nums = re.findall(r'[\d,]+', text)
            if nums:
                likes = nums[0].replace(",", "")
                break
        except Exception:
            continue

    return caption, likes, views, comments


# ── Main entry point ─────────────────────────────────────────────────────────

def scrape_reel(url):
    driver = None
    temp_dir = None
    try:
        print(f"[Scraper] Starting for: {url}")
        driver = _build_driver()
        temp_dir = getattr(driver, "_temp_profile_dir", None)

        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Wait for JS to fully settle — important for Instagram's React app
        time.sleep(5)

        # Detect login wall
        if "accounts/login" in driver.current_url:
            return {
                "error": (
                    "Instagram showed the login wall — session cookies didn't transfer. "
                    "Open Chrome, log into Instagram, then try again. "
                    f"(Profile: {REAL_PROFILE_PATH}\\{REAL_PROFILE_NAME})"
                )
            }

        # ── Run all four strategies ───────────────────────────────────────────
        print("[Scraper] Running extraction strategies...")

        caption_ld,  views_ld                            = _extract_from_ld_json(driver)
        caption_pj,  likes_pj, views_pj, comments_pj    = _extract_from_page_json(driver)
        caption_gq,  likes_gq, views_gq, comments_gq    = _extract_from_graphql(driver)
        caption_dom, likes_dom, views_dom, comments_dom  = _extract_from_dom(driver)

        print(f"[Scraper] ld+json   → caption={caption_ld[:30] if caption_ld != 'Not found' else 'x'}, views={views_ld}")
        print(f"[Scraper] page_json → caption={caption_pj[:30] if caption_pj != 'Not found' else 'x'}, views={views_pj}, likes={likes_pj}, comments={comments_pj}")
        print(f"[Scraper] graphql   → caption={caption_gq[:30] if caption_gq != 'Not found' else 'x'}, views={views_gq}, likes={likes_gq}, comments={comments_gq}")
        print(f"[Scraper] dom       → caption={caption_dom[:30] if caption_dom != 'Not found' else 'x'}, views={views_dom}, likes={likes_dom}")

        # Merge — prefer graphql > page_json > ld+json > dom
        NF = "Not found"
        caption  = next((v for v in [caption_gq,  caption_pj,  caption_ld,  caption_dom]  if v != NF), NF)
        likes    = next((v for v in [likes_gq,    likes_pj,    likes_dom]                 if v != NF), NF)
        views    = next((v for v in [views_gq,    views_pj,    views_ld,    views_dom]    if v != NF), NF)
        comments = next((v for v in [comments_gq, comments_pj, comments_dom]              if v != NF), NF)

        print(f"[Scraper] Final → views={views}, likes={likes}, comments={comments}")

        return {
            "caption":  caption,
            "likes":    likes,
            "views":    views,
            "comments": comments,
            "url":      url
        }

    except Exception as e:
        print(f"[Scraper] Exception: {e}")
        return {"error": str(e)}

    finally:
        if driver:
            driver.quit()
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"[Scraper] Cleaned up temp profile")
            except Exception:
                pass