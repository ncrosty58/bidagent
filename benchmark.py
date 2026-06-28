import asyncio
import time
from src.price_book import load_or_fetch_price_book

# Mock httpx to simulate slow network call
import httpx

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")

class MockClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, *args, **kwargs):
        await asyncio.sleep(0.5) # Simulate network latency
        return MockResponse({"data": {"services": [{"bidagentServiceKey": "test", "name": "Test"}]}})

import src.price_book
src.price_book.TWENTY_BASE_URL = "http://fake"
src.price_book.TWENTY_TOKEN = "fake_token"
src.price_book.httpx.AsyncClient = MockClient

async def benchmark():
    skill_def = {"services": {"test": {"display": "Test"}}}

    print("Baseline (5 calls):")
    start = time.time()
    for _ in range(5):
        await load_or_fetch_price_book(skill_def)
    end = time.time()

    print(f"Time taken: {end - start:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(benchmark())
