#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Float32, String
import tkinter as tk
from tkinter import ttk
import json
import subprocess
import os

class MotorGUI(Node):
    def __init__(self):
        super().__init__('motor_gui')

        # --- Lancement du sous-processus SWD Bridge ---
        self.get_logger().info("Lancement du pont SWD en arriere-plan...")
        script_dir = os.path.dirname(os.path.realpath(__file__))
        bridge_script = os.path.join(script_dir, 'motor_swd_bridge.py')
        self.bridge_process = subprocess.Popen(['python3', bridge_script])

        
        # Publishers
        self.pub_mode = self.create_publisher(Int32, '/motor/autonomous_mode', 10)
        self.pub_torque = self.create_publisher(Float32, '/motor/autonomous_torque', 10)
        
        # Subscriber for Telemetry
        self.sub_telemetry = self.create_subscription(String, '/motor/telemetry', self._cb_telemetry, 10)

        # Local state
        self.mode = 0
        self.torque = 0.0

        # Tkinter Setup
        self.root = tk.Tk()
        self.root.title("Controle et Telemetrie Moteur (ROS 2)")
        self.root.geometry("800x450")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Layout Frames
        left_frame = tk.Frame(self.root, width=400)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        right_frame = tk.LabelFrame(self.root, text=" Telemetrie en Temps Reel ", font=('Helvetica', 12, 'bold'))
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- LEFT FRAME (Controls) ---
        ttk.Label(left_frame, text="Interface ROS 2 - Moteur", font=('Helvetica', 14, 'bold')).pack(pady=10)
        
        self.mode_var = tk.StringVar(value="Activer Mode Autonome (OFF)")
        self.btn_mode = tk.Button(left_frame, textvariable=self.mode_var, command=self.toggle_mode,
                                  font=('Helvetica', 12), bg='tomato', fg='white', width=30, height=2)
        self.btn_mode.pack(pady=20)
        
        ttk.Label(left_frame, text="Consigne Courant Iq (A) :", font=('Helvetica', 10)).pack(pady=5)
        self.torque_var = tk.DoubleVar(value=0.0)
        self.slider = ttk.Scale(left_frame, from_=0.0, to=7.0, orient='horizontal', 
                                variable=self.torque_var, command=self.on_slider_change, length=300)
        self.slider.pack(pady=5)
        
        self.lbl_torque = ttk.Label(left_frame, text="0.00 A", font=('Helvetica', 12, 'bold'))
        self.lbl_torque.pack(pady=5)
        
        # --- RIGHT FRAME (Telemetry) ---
        self.tel_labels = {}
        telemetry_keys = [
            ("CurrentFaults", "Defauts Actifs"),
            ("PastFaults", "Historique Defauts"),
            ("SpeedSTO", "Vitesse STO"),
            ("SpeedVirtual", "Vitesse Virtuelle"),
            ("start", "Signal Start"),
            ("ack", "Signal Ack"),
            ("Iq", "Courant Iq Mesure"),
            ("PotData", "ADC Potentiometre"),
            ("Power", "Puissance (W)")
        ]
        
        for key, display_name in telemetry_keys:
            frame = tk.Frame(right_frame)
            frame.pack(fill=tk.X, pady=2, padx=5)
            ttk.Label(frame, text=f"{display_name} :", font=('Helvetica', 10)).pack(side=tk.LEFT)
            lbl_val = ttk.Label(frame, text="---", font=('Helvetica', 10, 'bold'), foreground="blue")
            lbl_val.pack(side=tk.RIGHT)
            self.tel_labels[key] = lbl_val
            
        # Timer for ROS spin
        self.ros_timer = self.root.after(50, self.ros_spin)

    def _cb_telemetry(self, msg: String):
        try:
            data = json.loads(msg.data)
            for key, val in data.items():
                if key in self.tel_labels:
                    self.tel_labels[key].config(text=str(val))
        except Exception as e:
            self.get_logger().error(f"Erreur parsing telemetrie: {e}")

    def toggle_mode(self):
        if self.mode == 0:
            self.mode = 1
            self.mode_var.set("Mode Autonome Actif (ON)")
            self.btn_mode.config(bg='medium sea green')
        else:
            self.mode = 0
            self.mode_var.set("Activer Mode Autonome (OFF)")
            self.btn_mode.config(bg='tomato')
            
        msg = Int32()
        msg.data = self.mode
        self.pub_mode.publish(msg)

    def on_slider_change(self, val):
        self.torque = float(val)
        self.lbl_torque.config(text=f"{self.torque:.2f} A")
        
        msg = Float32()
        msg.data = self.torque
        self.pub_torque.publish(msg)

    def ros_spin(self):
        rclpy.spin_once(self, timeout_sec=0.01)
        if rclpy.ok():
            self.ros_timer = self.root.after(50, self.ros_spin)

    def on_closing(self):
        msg_mode = Int32()
        msg_mode.data = 0
        self.pub_mode.publish(msg_mode)
        
        msg_torque = Float32()
        msg_torque.data = 0.0
        self.pub_torque.publish(msg_torque)
        
        # --- Arrêt du sous-processus SWD Bridge ---
        if hasattr(self, 'bridge_process') and self.bridge_process:
            self.get_logger().info("Arret du pont SWD...")
            self.bridge_process.terminate()
            self.bridge_process.wait()
        
        self.root.destroy()
        rclpy.shutdown()

    def run(self):
        self.root.mainloop()

def main(args=None):
    rclpy.init(args=args)
    gui = MotorGUI()
    gui.run()

if __name__ == '__main__':
    main()
