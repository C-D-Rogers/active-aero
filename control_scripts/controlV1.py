#!/usr/bin/env python3
import smbus2
import time
import numpy as np
import RPi.GPIO as GPIO
import math
import tkinter as tk
from tkinter import ttk
import csv
from datetime import datetime

import sys
sys.path.append('/home/benchh1/active-aero/lib/python3.11/site-packages')
from adafruit_servokit import ServoKit

# PWM servo driver setup
kit = ServoKit(channels=8)

# MPU6050 setup
MPU6050_ADDR = 0x69
bus = smbus2.SMBus(1)

# Logging setup
log_filename = f"wing_data_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
logging_active = False

# Initialize MPU6050
def init_gyro_accel():
    bus.write_byte_data(MPU6050_ADDR, 0x6B, 0)  # Wake up the MPU6050

# Read raw data from MPU6050
def read_raw_data(addr):
    high = bus.read_byte_data(MPU6050_ADDR, addr)
    low = bus.read_byte_data(MPU6050_ADDR, addr + 1)
    value = (high << 8) | low
    if value > 32768:
        value -= 65536
    return value

# Convert raw data to acceleration (in g) and gyro data (in degrees/sec)
def get_sensor_data():
    accel_x = read_raw_data(0x3B) / 16384.0
    accel_y = read_raw_data(0x3D) / 16384.0
    accel_z = read_raw_data(0x3F) / 16384.0

    gyro_x = read_raw_data(0x43) / 131.0
    gyro_y = read_raw_data(0x45) / 131.0
    gyro_z = read_raw_data(0x47) / 131.0

    return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z

# Control the servo angle
def set_servo_angle(angle):
    kit.servo[0].angle = 180 - angle
    kit.servo[1].angle = angle
    return angle

# Log data to CSV
def log_data(timestamp, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, speed, wing_angle):
    if logging_active:
        with open(log_filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, speed, wing_angle])

# Active wing control logic
def control_wing(curr_angle,accel_x_offset,accel_y_offset,accel_z_offset,gyro_x_offset,gyro_y_offset,gyro_z_offset):
    accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z = get_sensor_data()
    accel_x = accel_x - accel_x_offset
    accel_y = accel_y - accel_y_offset
    accel_z = accel_z - accel_z_offset
    gyro_x = gyro_x - gyro_x_offset
    gyro_y = accel_y - gyro_y_offset
    gyro_z = gyro_z - gyro_z_offset
    print("ACCELERATION")
    print("x " , accel_x)
    print("y " , accel_y)
    print("z " , accel_z)

    print("\nGYROSCOPE")
    print("x " , gyro_x)
    print("y " , gyro_y)
    print("z " , gyro_z)

    angle = 0

    # Adjust wing based on speed, acceleration, and turning
    if gyro_x < -.5:
        angle = 180  # Braking
        print("braking: set angle to 180")
    #elif abs(gyro_y) > 30:
    #    angle = 30 if gyro_y > 0 else -30  # Cornering
    #elif speed > 5:
    #    angle = 0  # Flatten for high speeds
    else:
        angle = 90  # Neutral position
        print("neutral position: set angle to 90")

    if curr_angle != angle:
        print("no change in curr_angle ", curr_angle)
        new_angle = set_servo_angle(angle)
        return new_angle
    return curr_angle

    # Update GUI and log data
    update_sensor_labels(accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, speed, angle)
    log_data(datetime.now().strftime('%H:%M:%S.%f'), accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, speed, angle)

# Read calibration parameters from CSV
def read_cal_params(filename):
    cal_offsets = np.array([ [], [], [],
                             [], [], [] ], dtype=object)  # cal vector
    with open(filename, mode='r') as file:
        reader = csv.reader(file)
        iter_ii = 0
        for row in reader:
            if len(row) > 2:
                row_vals = [float(ii) for ii in row[int((len(row)/2) + 1):]]
                cal_offsets[iter_ii] = row_vals
            else:
                cal_offsets[iter_ii] = float(row[1])
            iter_ii += 1
    return cal_offsets

# GUI Setup
class WingControlGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Active Wing Control")
        self.geometry("500x500")

        self.auto_mode = tk.BooleanVar(value=True)

        # Labels for sensor data
        self.accel_label = ttk.Label(self, text="Accelerometer: (X, Y, Z)")
        self.accel_label.pack(pady=5)

        self.gyro_label = ttk.Label(self, text="Gyroscope: (X, Y, Z)")
        self.gyro_label.pack(pady=5)

        self.speed_label = ttk.Label(self, text="Speed: 0.00 m/s")
        self.speed_label.pack(pady=5)

        self.angle_label = ttk.Label(self, text="Current Wing Angle: 0°")
        self.angle_label.pack(pady=5)

        # Manual wing control slider
        self.slider_label = ttk.Label(self, text="Manual Wing Angle:")
        self.slider_label.pack(pady=5)

        self.angle_slider = ttk.Scale(self, from_=-45, to=45, orient="horizontal", command=self.manual_adjust)
        self.angle_slider.pack(pady=5)

        # Toggle for auto/manual mode
        self.auto_mode_check = ttk.Checkbutton(self, text="Automatic Mode", variable=self.auto_mode)
        self.auto_mode_check.pack(pady=10)

        # Logging status
        self.log_status = ttk.Label(self, text=f"Logging to {log_filename}")
        self.log_status.pack(pady=5)

        # Start the update loop
        self.update_loop()

    def manual_adjust(self, value):
        if not self.auto_mode.get():
            angle = float(value)
            set_servo_angle(angle)
            accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z = get_sensor_data()
            speed = calculate_speed()
            update_sensor_labels(accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, speed, angle)
            log_data(datetime.now().strftime('%H:%M:%S.%f'), accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, speed, angle)

    def update_loop(self):
        if self.auto_mode.get():
            control_wing()
        self.after(50, self.update_loop)

# Update sensor labels on the GUI
def update_sensor_labels(accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, speed, angle):
    app.accel_label.config(text=f"Accelerometer: X={accel_x:.2f}, Y={accel_y:.2f}, Z={accel_z:.2f}")
    app.gyro_label.config(text=f"Gyroscope: X={gyro_x:.2f}, Y={gyro_y:.2f}, Z={gyro_z:.2f}")
    app.speed_label.config(text=f"Speed: {speed:.2f} m/s")
    app.angle_label.config(text=f"Current Wing Angle: {angle:.1f}°")

def bootcal():
    CalSamples = 100
    accel_x_cal = [j for j in range(CalSamples)] 
    accel_y_cal = [j for j in range(CalSamples)] 
    accel_z_cal = [j for j in range(CalSamples)] 
    gyro_x_cal = [j for j in range(CalSamples)] 
    gyro_y_cal = [j for j in range(CalSamples)] 
    gyro_z_cal = [j for j in range(CalSamples)] 
    for i in range(CalSamples):
        accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z = get_sensor_data()
        accel_x_cal[i] = accel_x
        accel_y_cal[i] = accel_y
        accel_z_cal[i] = accel_z
        gyro_x_cal[i] = gyro_x
        gyro_y_cal[i] = gyro_y
        gyro_z_cal[i] = gyro_z
        time.sleep(.1)
    accel_x_offset = sum(accel_x_cal)/CalSamples
    accel_y_offset = sum(accel_y_cal)/CalSamples
    accel_z_offset = sum(accel_z_cal)/CalSamples
    gyro_x_offset = sum(gyro_x_cal)/CalSamples
    gyro_y_offset = sum(gyro_y_cal)/CalSamples
    gyro_z_offset = sum(gyro_z_cal)/CalSamples
    print(accel_x_offset)
    print(accel_y_offset)
    print(accel_z_offset)
    print(gyro_x_offset)
    print(gyro_y_offset)
    print(gyro_z_offset)
    print('Calibration Complete')
    time.sleep(1)
    return accel_x_offset,accel_y_offset,accel_z_offset,gyro_x_offset,gyro_y_offset,gyro_z_offset
# Main function
if __name__ == "__main__":
    try:
#        calibration_offsets = read_cal_params("calibration.csv")
#        print(calibration_offsets)
        init_gyro_accel()
        accel_x_offset,accel_y_offset,accel_z_offset,gyro_x_offset,gyro_y_offset,gyro_z_offset = bootcal()
        curr_angle = 0;
        testval = 0
        while True:
            new_angle = control_wing(curr_angle,accel_x_offset,accel_y_offset,accel_z_offset,gyro_x_offset,gyro_y_offset,gyro_z_offset)
            time.sleep(.5)
            curr_angle = new_angle
            testval = testval + 1
            match testval:
                case 10:
                    print('Hold Car 90 degrees (driver side down)')
                    time.sleep(5)
                case 20:
                    print('Level Car')
                    time.sleep(5)
                case 30:
                    print('Hold Car 90 degrees (driver side up)')
                    time.sleep(5)
                case 40:
                    print('Test Complete')
                    break
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\nstopping execution\n\n")
        set_servo_angle(180)
        GPIO.cleanup()
