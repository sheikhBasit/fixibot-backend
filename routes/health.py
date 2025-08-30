from fastapi import APIRouter, Request
from datetime import datetime, timezone
import psutil
import socket
import platform
from typing import Dict, Any
from fastapi.responses import JSONResponse
import time
from config import settings
import logging
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/health", tags=["System Health"])
logger = logging.getLogger(__name__)

async def get_system_metrics() -> Dict[str, Any]:
    """Collect comprehensive system health metrics."""
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        load_avg = psutil.getloadavg()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "hostname": socket.gethostname(),
                "os": f"{platform.system()} {platform.release()}",
                "uptime_seconds": int(datetime.now().timestamp() - psutil.boot_time()),
            },
            "cpu": {
                "cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "usage_percent": psutil.cpu_percent(interval=1),
                "load_avg_1min": load_avg[0],
                "load_avg_5min": load_avg[1],
                "load_avg_15min": load_avg[2],
            },
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "used_percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "free_percent": round(disk.free / disk.total * 100, 2),
            },
            "network": {
                "host_ip": socket.gethostbyname(socket.gethostname()),
                "connections": len(psutil.net_connections()),
            }
        }
    except Exception as e:
        logger.error(f"Failed to collect system metrics: {str(e)}")
        return {
            "error": f"Failed to collect metrics: {str(e)}",
            "available_metrics": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system": {
                    "hostname": socket.gethostname(),
                    "os": f"{platform.system()} {platform.release()}",
                }
            }
        }

async def check_service_dependencies(mongo_client) -> Dict[str, Dict[str, Any]]:
    """Check status of critical service dependencies."""
    return {
        "database": await check_mongodb_connection(mongo_client)
    }

async def check_mongodb_connection(mongo_client) -> Dict[str, Any]:
    """Check MongoDB connection status and latency."""
    if not mongo_client:
        return {"status": "disconnected", "error": "MongoDB client not initialized"}
    
    try:
        start_time = time.time()
        await mongo_client.admin.command('ping')  # Use the passed client
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        server_info = await mongo_client.admin.command('buildInfo')
        db = mongo_client[settings.MONGO_DB]  # Get database from client
        
        return {
            "status": "connected",
            "latency_ms": latency_ms,
            "version": server_info.get("version"),
            "host": str(settings.MONGODB_URL).split("@")[-1].split("/")[0],
            "ok": 1.0,
            "collections": {
                "users": await db.users.count_documents({}),
                "mechanics": await db.mechanics.count_documents({}),
                "vehicles": await db.vehicles.count_documents({}),
            }
        }
    except Exception as e:
        logger.error(f"MongoDB connection check failed: {str(e)}")
        return {"status": "disconnected", "error": str(e)}

@router.get(
    "/",
    summary="Comprehensive System Health Check",
    response_description="Detailed system health metrics"
)
async def health_check(request: Request):
    """
    Comprehensive health check endpoint
    """
    try:
        # Get the MongoDB client from app.state, not request.state
        mongo_client = request.app.state.mongo_client  # ← FIX THIS LINE
        
        metrics = await get_system_metrics()
        dependencies = await check_service_dependencies(mongo_client)  # ← PASS THE CLIENT
        
        health_status = {
            "status": "healthy",
            "timestamp": metrics["timestamp"],
            "system": metrics["system"],
            "resources": {
                "cpu_usage": metrics["cpu"]["usage_percent"],
                "memory_usage": metrics["memory"]["used_percent"],
                "disk_free": metrics["disk"]["free_percent"],
            },
            "dependencies": dependencies,
        }

        critical_errors = [
            f"{service} service is unavailable: {status['error']}"
            for service, status in dependencies.items()
            if status.get("status") != "connected"
        ]

        if critical_errors:
            health_status.update({
                "status": "unhealthy",
                "critical_errors": critical_errors
            })
            return JSONResponse(content=health_status, status_code=503)
        
        return health_status
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": "Failed to perform health check",
                "error": str(e)
            },
            status_code=500
        )   