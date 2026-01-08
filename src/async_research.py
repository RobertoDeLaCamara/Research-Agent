import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional
from config import settings
from cache import cache_research
from metrics import metrics
from utils import api_call_with_retry

logger = logging.getLogger(__name__)

class AsyncResearchManager:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @metrics.time_operation("async_web_search")
    async def search_web_async(self, topic: str) -> List[dict]:
        """Async web search."""
        try:
            # Simulate async web search (replace with actual implementation)
            await asyncio.sleep(0.1)  # Simulate API call
            return [{"content": f"Web result for {topic}", "url": "example.com"}]
        except Exception as e:
            logger.error(f"Async web search failed: {e}")
            return []
    
    @metrics.time_operation("async_wiki_search")
    async def search_wiki_async(self, topic: str) -> List[dict]:
        """Async Wikipedia search."""
        try:
            await asyncio.sleep(0.1)  # Simulate API call
            return [{"title": f"Wiki: {topic}", "summary": f"Wikipedia content for {topic}"}]
        except Exception as e:
            logger.error(f"Async wiki search failed: {e}")
            return []
    
    @metrics.time_operation("async_arxiv_search")
    async def search_arxiv_async(self, topic: str) -> List[dict]:
        """Async arXiv search."""
        try:
            await asyncio.sleep(0.1)  # Simulate API call
            return [{"title": f"arXiv: {topic}", "summary": f"Academic paper about {topic}"}]
        except Exception as e:
            logger.error(f"Async arXiv search failed: {e}")
            return []
    
    @metrics.time_operation("async_github_search")
    async def search_github_async(self, topic: str) -> List[dict]:
        """Async GitHub search."""
        try:
            await asyncio.sleep(0.1)  # Simulate API call
            return [{"name": f"repo-{topic}", "description": f"GitHub repo for {topic}"}]
        except Exception as e:
            logger.error(f"Async GitHub search failed: {e}")
            return []
    
    async def parallel_research(self, topic: str) -> Dict[str, List[dict]]:
        """Run all research sources in parallel."""
        logger.info(f"Starting parallel research for: {topic}")
        
        # Create tasks for parallel execution
        tasks = {
            'web': self.search_web_async(topic),
            'wiki': self.search_wiki_async(topic),
            'arxiv': self.search_arxiv_async(topic),
            'github': self.search_github_async(topic)
        }
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Combine results
        combined_results = {}
        for i, (source, task) in enumerate(tasks.items()):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Error in {source} search: {result}")
                combined_results[f"{source}_research"] = []
            else:
                combined_results[f"{source}_research"] = result
        
        logger.info("Parallel research completed")
        return combined_results

async def run_parallel_research(topic: str) -> Dict[str, List[dict]]:
    """Main function to run parallel research."""
    async with AsyncResearchManager() as manager:
        return await manager.parallel_research(topic)
