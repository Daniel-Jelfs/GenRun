import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

# Setup templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint for Render"""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "cron_schedule": f"{settings.cron_hour:02d}:{settings.cron_minute:02d} UTC",
        "region": scheduler.get_region()
    }


@app.get("/api/status")
async def api_status():
    """API status endpoint"""
    return {
        "name": "Dropshipping Trend Detector",
        "version": "1.0.0",
        "status": "running",
        "region": scheduler.get_region()
    }


@app.get("/api/region")
async def get_region():
    """Get current region"""
    return {
        "region": scheduler.get_region(),
        "available_regions": ["US", "UK"]
    }


@app.post("/api/region/{region}")
async def set_region(region: str):
    """Set the region for scraping"""
    region = region.upper()
    if region not in ["US", "UK"]:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Invalid region: {region}. Use 'US' or 'UK'"}
        )
    
    scheduler.set_region(region)
    return {
        "success": True,
        "region": region,
        "message": f"Region set to {region}. New scans will use Amazon {region}."
    }


@app.get("/api/products")
async def get_products(limit: int = 100):
    """Get all products for the dashboard"""
    try:
        products = db.get_top_trending_products(limit=limit)
        return {
            "success": True,
            "count": len(products),
            "products": products,
            "region": scheduler.get_region()
        }
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "products": []}
        )


@app.get("/api/trends")
async def get_trends(limit: int = 10):
    """Get top trending products"""
    try:
        products = db.get_top_trending_products(limit=limit)
        return {
            "success": True,
            "count": len(products),
            "products": products,
            "region": scheduler.get_region()
        }
    except Exception as e:
        logger.error(f"Error fetching trends: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/trigger-scan")
async def trigger_scan(region: str = None):
    """Manually trigger a trend detection scan"""
    try:
        current_region = scheduler.get_region()
        scan_region = region.upper() if region else current_region
        
        if scan_region not in ["US", "UK"]:
            scan_region = current_region
        
        logger.info(f"Manual scan triggered via API for region: {scan_region}")
        
        # Run in background
        asyncio.create_task(scheduler.run_trend_detection(region=scan_region))
        
        return {
            "success": True,
            "message": f"Trend detection scan started for Amazon {scan_region}",
            "region": scan_region
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
