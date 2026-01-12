import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio

from app.config import settings
from app.scheduler import scheduler
from app.database import db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Dropshipping Trend Detection System...")
    logger.info(f"Environment: {settings.environment}")
    
    # Initialize database
    await db.init_tables()
    
    # Start scheduler
    scheduler.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()


# Create FastAPI app
app = FastAPI(
    title="Dropshipping Trend Detector",
    description="Automated trend detection for dropshipping products",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Dropshipping Trend Detector",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint for Render"""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "cron_schedule": f"{settings.cron_hour:02d}:{settings.cron_minute:02d} UTC"
    }


@app.get("/api/trends")
async def get_trends(limit: int = 10):
    """Get top trending products"""
    try:
        products = db.get_top_trending_products(limit=limit)
        return {
            "success": True,
            "count": len(products),
            "products": products
        }
    except Exception as e:
        logger.error(f"Error fetching trends: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/trigger-scan")
async def trigger_scan():
    """Manually trigger a trend detection scan"""
    try:
        logger.info("Manual scan triggered via API")
        # Run in background
        asyncio.create_task(scheduler.run_trend_detection())
        return {
            "success": True,
            "message": "Trend detection scan started"
        }
    except Exception as e:
        logger.error(f"Error triggering scan: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
