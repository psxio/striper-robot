"""striper_pathgen — path generation for autonomous parking lot line striping."""

from .models import (
    GeoPoint,
    PaintJob,
    PaintPath,
    PaintSegment,
    Point2D,
    TransitPath,
)
from .coordinate_transform import CoordinateTransformer
from .path_optimizer import calculate_total_transit_distance, optimize_path_order
from .template_generator import (
    generate_arrow,
    generate_crosswalk,
    generate_from_template,
    generate_handicap_space,
    generate_parking_row,
    generate_standard_space,
    load_template,
    save_template,
)
from .ros_converter import msg_to_paint_path, paint_job_to_msgs, paint_path_to_msg
from .job_exporter import export_csv, export_geojson, export_kml
from .mission_planner import export_waypoints, save_waypoints

__all__ = [
    # Models
    "Point2D",
    "GeoPoint",
    "PaintPath",
    "TransitPath",
    "PaintSegment",
    "PaintJob",
    # Coordinate transforms
    "CoordinateTransformer",
    # Path optimizer
    "optimize_path_order",
    "calculate_total_transit_distance",
    # Template generators
    "generate_standard_space",
    "generate_handicap_space",
    "generate_parking_row",
    "generate_arrow",
    "generate_crosswalk",
    "generate_from_template",
    "load_template",
    "save_template",
    # ROS converter
    "paint_path_to_msg",
    "paint_job_to_msgs",
    "msg_to_paint_path",
    # Job exporters
    "export_geojson",
    "export_kml",
    "export_csv",
    # Mission Planner / ArduPilot
    "export_waypoints",
    "save_waypoints",
]
