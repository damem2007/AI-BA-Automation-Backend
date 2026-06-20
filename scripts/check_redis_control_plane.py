from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.control_plane import control_plane


def main() -> None:
    metrics = control_plane.metrics()
    backend = metrics.get("control_plane")
    if backend != "redis":
        raise SystemExit(
            "Redis control plane is not active. "
            "Set REDIS_URL and start local Redis before running enterprise-mode checks."
        )
    print("Redis control plane: ok")
    print(metrics)


if __name__ == "__main__":
    main()
