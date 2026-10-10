#!/usr/bin/env python3
"""
Noeud ROS2 : motor_swd_bridge
==============================
Commande le moteur STM32 (ENIMIAXEdition_Motor_MicroROS) via SWD/pyOCD.
Les variables sont ecrites directement dans la RAM du STM32 sans Micro-ROS.

Adresses RAM fixes (section .ros2_iface dans le linker script) :
  autonomousMode   @ 0x20007FF0  (int32,  0 = stop | 1 = actif)
  autonomousTorque @ 0x20007FF4  (float32, courant Iq en A, limite 7 A)

Topics ROS2 :
  /motor/autonomous_mode   (std_msgs/msg/Int32)   0=stop, 1=actif
  /motor/autonomous_torque (std_msgs/msg/Float32) courant en A (0.0 a 7.0)

Dependances :
  pip install pyocd
  sudo apt install python3-colcon-common-extensions  (pour ROS2)

Usage :
  source /opt/ros/<distro>/setup.bash
  python3 motor_swd_bridge.py
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Float32
import struct
import threading

# ── Adresses RAM fixes (CubeMonitor / ELF) ──────────────────────────
ADDR_AUTONOMOUS_MODE    = 0x2000048C   # int32 (Signed 32-bit)
ADDR_AUTONOMOUS_TORQUE  = 0x20000488   # float32 (Float)

# ── Limite de securite ────────────────────────────────────────────────────────
TORQUE_MAX_NM = 7.0


class MotorSWDBridge(Node):
    """Pont ROS2 <-> STM32 via SWD/pyOCD."""

    def __init__(self):
        super().__init__('motor_swd_bridge')

        # ── Connexion pyOCD ───────────────────────────────────────────────────
        self._session = None
        self._target  = None
        self._lock    = threading.Lock()
        self._connect_ocd()

        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(
            Int32,
            '/motor/autonomous_mode',
            self._cb_mode,
            10
        )
        self.create_subscription(
            Float32,
            '/motor/autonomous_torque',
            self._cb_torque,
            10
        )

        # ── Telemetry Publisher ───────────────────────────────────────────────
        from std_msgs.msg import String
        self.telemetry_pub = self.create_publisher(String, '/motor/telemetry', 10)
        self.timer = self.create_timer(0.1, self._publish_telemetry) # 10 Hz

        self.get_logger().info(
            'motor_swd_bridge demarre. '
            'autonomousMode @ 0x{:08X}, autonomousTorque @ 0x{:08X}'.format(
                ADDR_AUTONOMOUS_MODE, ADDR_AUTONOMOUS_TORQUE
            )
        )

    # ── Connexion SWD ─────────────────────────────────────────────────────────
    def _connect_ocd(self):
        try:
            from pyocd.core.helpers import ConnectHelper
            self._session = ConnectHelper.session_with_chosen_probe(
                target_override='stm32g431vbtx',   # cible exacte
                frequency=4000000,                  # 4 MHz SWD
            )
            self._session.open()
            self._target = self._session.target
            self._target.reset_and_halt()           # reset pour synchroniser
            self._target.resume()                   # reprendre l'execution
            self.get_logger().info('ST-Link connecte via pyOCD.')
        except Exception as e:
            self.get_logger().error(f'Erreur connexion pyOCD : {e}')
            self.get_logger().error(
                'Verifiez : ST-Link branche, permissions USB (usbipd pour WSL2).'
            )

    # ── Ecriture SWD ─────────────────────────────────────────────────────────
    def _write_int32(self, addr: int, value: int):
        if self._target is None:
            return
        with self._lock:
            try:
                data = struct.pack('<i', value)
                self._target.write_memory_block8(addr, list(data))
                self.get_logger().debug(f'[SWD] 0x{addr:08X} <- int32({value})')
            except Exception as e:
                self.get_logger().error(f'Erreur ecriture int32 @ 0x{addr:08X}: {e}')

    def _write_float32(self, addr: int, value: float):
        if self._target is None:
            return
        with self._lock:
            try:
                data = struct.pack('<f', value)
                self._target.write_memory_block8(addr, list(data))
                self.get_logger().debug(f'[SWD] 0x{addr:08X} <- float32({value:.4f})')
            except Exception as e:
                self.get_logger().error(f'Erreur ecriture float32 @ 0x{addr:08X}: {e}')

    def _read_int16(self, addr: int):
        val = self._target.read16(addr)
        return val if val <= 0x7FFF else val - 0x10000

    def _read_uint16(self, addr: int):
        return self._target.read16(addr)

    def _read_int32(self, addr: int):
        val = self._target.read32(addr)
        return val if val <= 0x7FFFFFFF else val - 0x100000000

    def _publish_telemetry(self):
        if self._target is None:
            return
        with self._lock:
            try:
                import json
                from std_msgs.msg import String
                data = {
                    "CurrentFaults": self._read_uint16(0x2000000A),
                    "PastFaults": self._read_uint16(0x2000000C),
                    "SpeedSTO": self._read_int16(0x2000007C),
                    "SpeedVirtual": self._read_int16(0x20000420),
                    "start": self._read_int32(0x20000004),
                    "ack": self._read_int32(0x20000000),
                    "Iq": self._read_int16(0x200006A4),
                    "PotData": self._read_uint16(0x200003D2),
                    "Power": self._read_int16(0x20000394)
                }
                msg = String()
                msg.data = json.dumps(data)
                self.telemetry_pub.publish(msg)
            except Exception as e:
                self.get_logger().debug(f'Erreur lecture telemetrie : {e}')
    def _cb_mode(self, msg: Int32):
        mode = 1 if msg.data != 0 else 0
        self._write_int32(ADDR_AUTONOMOUS_MODE, mode)
        self.get_logger().info(f'autonomousMode <- {mode}')

    def _cb_torque(self, msg: Float32):
        torque = max(0.0, min(float(msg.data), TORQUE_MAX_NM))  # clamp securite
        if torque != float(msg.data):
            self.get_logger().warn(
                f'Courant demande {msg.data:.2f} A depasse la limite {TORQUE_MAX_NM} A -> clamp.'
            )
        self._write_float32(ADDR_AUTONOMOUS_TORQUE, torque)
        self.get_logger().info(f'autonomousTorque <- {torque:.4f} A')

    # ── Nettoyage ─────────────────────────────────────────────────────────────
    def destroy_node(self):
        # Stop moteur avant de fermer
        if self._target:
            self._write_int32(ADDR_AUTONOMOUS_MODE, 0)
            self._write_float32(ADDR_AUTONOMOUS_TORQUE, 0.0)
        if self._session:
            self._session.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MotorSWDBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
