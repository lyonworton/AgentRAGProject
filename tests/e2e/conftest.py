import pytest
import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:3000/api/v1"
CREDENTIALS = {"username": "admin", "password": "admin"}


@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        pg = await ctx.new_page()
        yield pg
        await ctx.close()
        await browser.close()


@pytest.fixture(scope="session")
async def client():
    """Shared httpx client with timeout."""
    async with httpx.AsyncClient(timeout=30) as c:
        yield c


@pytest.fixture(scope="session")
async def auth_token(client: httpx.AsyncClient):
    """Get a valid auth token for admin user (cached per session)."""
    resp = await client.post(f"{API_URL}/auth/login", json=CREDENTIALS)
    data = resp.json()
    return data["access_token"]


@pytest.fixture(scope="session")
async def collection_id(client: httpx.AsyncClient, auth_token: str):
    """Ensure a test collection exists, return its id."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = await client.get(f"{API_URL}/collections", headers=headers)
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", data.get("data", []))
    if items:
        if isinstance(items[0], dict):
            return items[0].get("id") or items[0].get("collection_id")
        return items[0]

    resp = await client.post(
        f"{API_URL}/collections",
        json={"name": "E2E Test Collection", "description": "Auto-created for E2E tests"},
        headers=headers,
    )
    result = resp.json()
    return result.get("id") or result.get("collection_id")


@pytest.fixture
async def authenticated_page(page, auth_token: str, collection_id: str):
    """Navigate to frontend, inject auth token, and ensure chat is ready."""
    await page.goto(f"{BASE_URL}/login")
    await page.evaluate(f"localStorage.setItem('token', {auth_token!r})")
    # Reload so AuthContext picks up token, then navigate
    await page.reload()
    await page.goto(f"{BASE_URL}/chat")
    await page.wait_for_selector(
        "input[placeholder='Ask a question...']", state="visible", timeout=10000
    )
    # Wait for collection to load (no "Create a collection" message)
    try:
        await page.wait_for_selector("text=E2E Test Collection", state="visible", timeout=5000)
    except Exception:
        pass  # May have loaded other collections
    yield page