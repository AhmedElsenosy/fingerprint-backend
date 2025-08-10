import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
HOST_REMOTE_URL = os.getenv("HOST_REMOTE_URL")


async def check_internet_connectivity(timeout: int = 5) -> bool:
    """
    Check if we have internet connectivity by trying to reach the remote backend.
    
    Args:
        timeout: Timeout in seconds for the connection attempt
        
    Returns:
        bool: True if internet is available, False otherwise
    """
    if not HOST_REMOTE_URL:
        return False
        
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try to make a simple request to the remote backend
            # We'll use the next-ids endpoint since we know it exists
            response = await client.get(f"{HOST_REMOTE_URL}/students/next-ids", timeout=timeout)
            return response.status_code in [200, 401]  # 401 means server is reachable but needs auth
    except (httpx.RequestError, httpx.TimeoutException, Exception):
        return False


def check_internet_connectivity_sync(timeout: int = 5) -> bool:
    """
    Synchronous version of internet connectivity check.
    
    Args:
        timeout: Timeout in seconds for the connection attempt
        
    Returns:
        bool: True if internet is available, False otherwise
    """
    try:
        return asyncio.run(check_internet_connectivity(timeout))
    except Exception:
        return False
