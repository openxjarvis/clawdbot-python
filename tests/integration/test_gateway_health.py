"""Integration tests for gateway health endpoints"""

import asyncio
import pytest
from openclaw.monitoring.health import HealthCheck, ComponentHealth, HealthStatus


@pytest.mark.asyncio
async def test_gateway_health_check_integration():
    """Test full health check integration"""
    health = HealthCheck()

    async def check_runtime():
        return ComponentHealth(
            name="runtime",
            status=HealthStatus.HEALTHY,
            message="Runtime initialized",
        )

    async def check_sessions():
        return ComponentHealth(
            name="sessions",
            status=HealthStatus.HEALTHY,
            message="0 sessions",
            details={"count": 0},
        )

    health.register("runtime", check_runtime, critical=True)
    health.register("sessions", check_sessions)

    # check_all returns HealthCheckResponse
    health_response = await health.check_all()

    assert health_response.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
    assert len(health_response.components) >= 2

    # Verify liveness
    assert await health.liveness() is True


@pytest.mark.asyncio
async def test_health_check_with_failures():
    """Test health check handling of component failures"""
    health = HealthCheck()

    async def failing_check():
        raise RuntimeError("Simulated component failure")

    async def healthy_check():
        return ComponentHealth(
            name="healthy",
            status=HealthStatus.HEALTHY,
        )

    health.register("failing", failing_check, critical=True)
    health.register("healthy", healthy_check)

    # check_all returns HealthCheckResponse
    results = await health.check_all()

    # HealthCheckResponse.components is a dict[str, dict]
    assert "failing" in results.components
    assert results.components["failing"]["status"] == HealthStatus.UNHEALTHY

    assert "healthy" in results.components
    assert results.components["healthy"]["status"] == HealthStatus.HEALTHY

    # Overall health should be unhealthy due to critical component
    assert results.status == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_readiness_probe_integration():
    """Test readiness probe with real components"""
    health = HealthCheck()

    initialized = {"db": False}

    async def check_db():
        if initialized["db"]:
            return ComponentHealth(name="db", status=HealthStatus.HEALTHY)
        return ComponentHealth(name="db", status=HealthStatus.UNHEALTHY, message="Not initialized")

    async def check_cache():
        return ComponentHealth(name="cache", status=HealthStatus.HEALTHY, message="Optional")

    health.register("db", check_db, critical=True)
    health.register("cache", check_cache, critical=False)

    # Before initialization — db is critical and unhealthy
    ready = await health.readiness()
    assert ready is False

    # Initialize DB
    initialized["db"] = True
    ready = await health.readiness()
    assert ready is True
