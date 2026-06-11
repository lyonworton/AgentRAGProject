import asyncio, httpx, json

async def debug():
    async with httpx.AsyncClient(timeout=30) as c:
        # Login
        r = await c.post('http://localhost:3000/api/v1/auth/login',
                         json={'username':'admin','password':'admin'})
        token = r.json()['access_token']
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        # Create session
        body = {'collection_id': '66fd32051a5c4e8e', 'title': 'debug'}
        r = await c.post('http://localhost:3000/api/v1/sessions', json=body, headers=headers)
        print(f'sessions POST: {r.status_code}')
        print(r.text[:500])

asyncio.run(debug())