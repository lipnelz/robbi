import logging


def get_system_stats(logger) -> dict:
    """
    Get system statistics (CPU, RAM, Temperature)

    :param logger: The logger instance
    :return: json dict with system stats
    """
    try:
        import psutil
    except ImportError:
        if logger is None:
            logger = logging.getLogger()
        logger.error("psutil not installed")
        return {"error": "psutil library not installed"}

    if logger is None:
        logger = logging.getLogger()

    try:
        # Get per-core CPU usage (single blocking call) and derive overall average
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        cpu_overall = round(sum(cpu_per_core) / len(cpu_per_core), 1) if cpu_per_core else 0

        stats = {
            "cpu_percent": cpu_overall,
            "cpu_cores": [{"core": i, "percent": percent} for i, percent in enumerate(cpu_per_core)],
            "ram_percent": psutil.virtual_memory().percent,
            "ram_available_gb": round(psutil.virtual_memory().available / (1024 ** 3), 2),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2)
        }

        # Try to get temperature (Linux only)
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    temperature_details = []
                    for sensor_type, entries in temps.items():
                        for entry in entries:
                            temperature_details.append({
                                "sensor": sensor_type,
                                "label": entry.label or f"Sensor {len(temperature_details)}",
                                "current": round(entry.current, 1)
                            })
                    if temperature_details:
                        stats["temperature_details"] = temperature_details
                        all_temps = [t["current"] for t in temperature_details]
                        stats["temperature_avg"] = round(sum(all_temps) / len(all_temps), 1)
        except Exception as e:
            logger.warning(f"Could not retrieve temperature: {e}")

        return stats
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error: {str(e)}"}
