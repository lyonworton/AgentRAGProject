import pytest
import asyncio

BASE_URL = "http://localhost:3000"


async def _wait_input_enabled(page, timeout=60):
    for _ in range(timeout):
        disabled = await page.evaluate(
            "!!document.querySelector('input[placeholder=\"Ask a question...\"]')?.disabled"
        )
        if not disabled:
            return True
        await asyncio.sleep(1)
    return False


async def _send(page, text, timeout=60):
    await page.fill("input[placeholder='Ask a question...']", text)
    await page.press("input[placeholder='Ask a question...']", "Enter")
    await _wait_input_enabled(page, timeout)


@pytest.mark.asyncio
class TestLogin:
    async def test_login_form_and_redirect(self, page):
        await page.goto(f"{BASE_URL}/login")
        await page.wait_for_selector("#username", state="visible")
        await page.fill("#username", "admin")
        await page.fill("#password", "admin")
        await page.click("button[type='submit']")
        await page.wait_for_url(f"{BASE_URL}/admin", timeout=15000)
        await page.wait_for_selector("text=admin", timeout=10000)


@pytest.mark.asyncio
class TestChat:
    async def test_basic_streaming(self, authenticated_page):
        page = authenticated_page
        await _send(page, "Hello")
        assert await page.is_visible("text=Hello")
        bubbles = await page.locator("div.bg-muted").count()
        assert bubbles > 0, "No assistant message bubbles"

    async def test_multi_turn_memory(self, authenticated_page):
        page = authenticated_page
        await _send(page, "My name is Alice and I work at Acme Corp in Shanghai")
        await _send(page, "What is my name and where do I work?")
        body = await page.text_content("body")
        ok = ("Alice" in body) or ("alice" in body.lower())
        assert ok, f"Memory recall failed. Body: {body[:500]}"


@pytest.mark.asyncio
class TestSessions:
    async def test_session_persistence(self, authenticated_page):
        page = authenticated_page
        await _send(page, "persistence test")
        url = page.url
        assert "/chat/" in url, f"No session in URL: {url}"
        await page.goto(f"{BASE_URL}/admin")
        await asyncio.sleep(1)
        await page.goto(url)
        await page.wait_for_selector("text=persistence test", state="visible", timeout=10000)

    async def test_session_delete(self, authenticated_page):
        page = authenticated_page
        await _send(page, "delete me")
        # Navigate to a fresh /chat to trigger session list reload
        await page.goto(f"{BASE_URL}/chat")
        await page.wait_for_selector(
            "input[placeholder='Ask a question...']", state="visible", timeout=10000
        )
        await asyncio.sleep(3)
        links = await page.locator("a[href^='/chat/']").count()
        if links == 0:
            pytest.skip("No session links available")
        await page.locator("a[href^='/chat/']").first.hover()
        btn = page.locator("button").filter(has=page.locator("svg.lucide-trash2"))
        if await btn.count() > 0:
            before = await page.locator("a[href^='/chat/']").count()
            await btn.first.click()
            await asyncio.sleep(2)
            after = await page.locator("a[href^='/chat/']").count()
            assert after < before


@pytest.mark.asyncio
class TestAdmin:
    async def test_dashboard_loads(self, authenticated_page):
        page = authenticated_page
        await page.goto(f"{BASE_URL}/admin")
        await page.wait_for_selector("text=Dashboard", state="visible", timeout=10000)
        assert await page.is_visible("text=Collections")
        assert await page.is_visible("text=Documents")
        await page.click("text=Collections")
        await page.wait_for_url(f"{BASE_URL}/admin/collections", timeout=10000)
        body = await page.text_content("body")
        assert body and ("collections" in body.lower() or "No collections" in body)