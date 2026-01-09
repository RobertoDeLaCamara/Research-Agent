# src/main.py

import os
import argparse
import asyncio
from dotenv import load_dotenv
from agent import app
from utils import setup_logging, validate_env_vars
from validators import validate_topic
from health import check_dependencies
from progress import init_progress
from metrics import metrics
from config import settings

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Research-Agent: Multi-source AI Researcher")
    parser.add_argument(
        "topic",
        type=str,
        nargs="?",
        default="Artificial Intelligence in Education",
        help="Research topic to investigate (default: 'Artificial Intelligence in Education')"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=settings.log_level,
        help="Set logging level"
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip health checks on startup"
    )
    return parser.parse_args()

def run_agent():
    """Main function to configure and run the research agent."""
    load_dotenv()
    
    args = parse_args()
    logger = setup_logging(args.log_level)

    # Bypass proxy for Ollama before any service calls
    from utils import bypass_proxy_for_ollama
    bypass_proxy_for_ollama()
    
    try:
        # Validate topic
        validated_topic = validate_topic(args.topic)
        
        # Health checks
        if not args.skip_health_check:
            logger.info("Running health checks...")
            healthy, checks = check_dependencies()
            if not healthy:
                logger.warning("Some health checks failed, but continuing...")
        
        # Initialize progress tracking (12 total steps)
        init_progress(12)
        
        validate_env_vars()
        logger.info(f"Starting research agent for topic: '{validated_topic}'")
        
        initial_state = {"topic": validated_topic, "messages": []}
        app.invoke(initial_state)
        
        # Log final metrics
        metrics.log_stats()
        logger.info("Agent execution completed successfully")
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        metrics.increment("agent_failures")
        raise

if __name__ == "__main__":
    run_agent()