import numpy as np
import math

class WGS84Converter:
    """
    WGS-84 to Local Cartesian coordinate converter for real-world RTK streams.
    """
    def __init__(self, lat0: float, lon0: float):
        # Earth radius in meters
        self.R = 6378137.0 
        self.lat0 = math.radians(lat0)
        self.lon0 = math.radians(lon0)
        
    def to_local(self, lat: float, lon: float) -> tuple[float, float]:
        """Convert WGS-84 (lat, lon) to Local Cartesian (x, y) relative to origin."""
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        
        # Equirectangular approximation for fast local ADAS conversion
        x = self.R * (lon_rad - self.lon0) * math.cos(self.lat0)
        y = self.R * (lat_rad - self.lat0)
        return x, y

    def to_wgs84(self, x: float, y: float) -> tuple[float, float]:
        """Convert Local Cartesian (x, y) to WGS-84 (lat, lon)."""
        lat_rad = y / self.R + self.lat0
        lon_rad = x / (self.R * math.cos(self.lat0)) + self.lon0
        return math.degrees(lat_rad), math.degrees(lon_rad)


# ==============================================================================
# ROS2 Stub Wrapper
# ==============================================================================
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String # Placeholder for actual BSM J2735 messages
except ImportError:
    # Handle environment where ROS2 is not installed
    pass

class BSDEngineROS2Wrapper:
    """
    Standard ROS2 async subscriber wrapper around BSDEngine.
    
    5-Field BSM Pipeline (V3.0):
    1. Incoming J2735 BSM is decoded to extract: lat, lon, speed, accel_signed
    2. (lat, lon) → (x, y) via WGS84Converter.to_local()
    3. accel_signed → (accel=max(0,a), decel=max(0,-a))
    4. Raw BSM dict {vid, x, y, speed, accel, decel, vehicle_type, timestamp}
       is passed to BSMParser.parse() which derives heading, yaw_rate, net_accel
    5. Resulting VehicleState is fed to BSDEngine.process_step()
    """
    def __init__(self, bsd_engine, bsm_parser=None):
        from bsd_engine import BSMParser
        self.engine = bsd_engine
        self.parser = bsm_parser if bsm_parser else BSMParser()
        self.wgs84 = WGS84Converter(lat0=18.98, lon0=72.93)  # Atal Setu Bridge origin
        
        try:
            rclpy.init()
            self.node = Node("v2v_bsd_node")
            self.bsm_sub = self.node.create_subscription(
                String, 
                "/v2x/bsm_rx", 
                self.bsm_callback, 
                10
            )
            self.alert_pub = self.node.create_publisher(String, "/v2x/bsd_alerts", 10)
        except NameError:
            pass

    def bsm_callback(self, msg):
        """
        Async callback for incoming J2735 Basic Safety Messages.
        
        Decodes J2735, extracts 5 BSM fields, parses via BSMParser,
        then feeds to BSDEngine.
        """
        # bsm_data = decode_j2735(msg.data)
        # x, y = self.wgs84.to_local(bsm_data['latitude'], bsm_data['longitude'])
        # accel_signed = bsm_data['longitudinal_accel']
        #
        # raw_bsm = {
        #     'vid': bsm_data['temporary_id'],
        #     'x': x, 'y': y,
        #     'speed': bsm_data['speed'],
        #     'accel': max(0.0, accel_signed),   # BSM field 4
        #     'decel': max(0.0, -accel_signed),   # BSM field 5
        #     'vehicle_type': bsm_data.get('vehicle_class', 'sedan'),
        #     'timestamp': bsm_data.get('sec_mark', 0),
        # }
        #
        # target_state = self.parser.parse(raw_bsm)
        #
        # ego_state = get_current_ego_state()  # From local CAN bus / IMU
        # result = self.engine.process_step(ego_state, {target_state.vid: target_state},
        #                                    {target_state.vid})
        #
        # alert_msg = String()
        # alert_msg.data = json.dumps(result)
        # self.alert_pub.publish(alert_msg)
        pass

