from coercive import Coercive
import serial
import time
from os import _exit
from matplotlib import pyplot as plt
from statistics import pstdev, mean, median
from datetime import datetime as dt

from warnings import simplefilter
simplefilter(action='ignore', category=FutureWarning)
import pandas as pd

rpms = [500, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200]
# rpms = [200, 400, 600]

# Reverse direction time
rev_time = 3.0
# Thruster stop, wait after reversing
wai_time = 0.8
# Forward direction time
run_time = 4.0
# Load cell data acq time
acq_time = 3.0
# Thruster stop, water settling wait time
stp_time = 4.5 * 60
# stp_time = 5.0

voltage = 320

def main(ts, ms):
    t = Coercive(id = 1)
    
    thrusts = []
    currents = []
    read_rpms = []
    data = pd.DataFrame(columns=["Voltage", "Current", "Set RPM", "Read RPM", "Force", "Thrust"])

    print("Waiting to start...")
    time.sleep(5)

    test_time = dt.now()
    time_str = test_time.strftime("%H_%M_%S")
    print(f"Started at {test_time.strftime('H:%M:%S')}")

    run_open_loop = False

    for rpm in rpms:
        _forces = []
        _read_rpms = []
        _currents = []
        motor_data = []
        force = 0.0
        
        # Zero load cell
        ms.write(b'Z')
        time.sleep(1)

        init = time.time()
        
        # Reverse thruster
        print("Reversing thruster...")
        # Run reverse at half the rpm to get the water flowing in the opp dir
        pkt = t.generatePacketFromRPM(rpm/2, dir='r', openloop=run_open_loop)
        while(time.time() - init < rev_time):
            ts.write(pkt)

            motor_reply = []
            for _ in range(20):
                motor_reply.append(ts.read())
            motor_data.append(Coercive.parseReply(motor_reply, condensed=True))

            time.sleep(0.1)

        # Stop thruster
        pkt = t.generatePacketFromRPM(0, dir='f', openloop=run_open_loop)
        ts.write(pkt)
        time.sleep(wai_time)

        init = time.time()

        # Run thruster
        print(f"Running at {rpm} RPM for {run_time} s")
        pkt = t.generatePacketFromRPM(rpm, dir='f', openloop=run_open_loop)
        while(time.time() - init < run_time):
            ts.write(pkt)

            motor_reply = []
            for _ in range(20):
                motor_reply.append(ts.read())
            reply_decoded = Coercive.parseReply(motor_reply, condensed=True).split(',')
            motor_i = reply_decoded[3]
            motor_s = reply_decoded[1]

            # Read load cell from thruster-start until acq_time
            force_clean = 0.0
            force = ms.readline().decode()
            try:
                force_clean = float(force[2:-2])
            except ValueError:
                pass

            if (time.time() - init < acq_time):
                _forces.append(force_clean)
                _read_rpms.append(int(motor_s))
                _currents.append(float(motor_i))

            row = {"Voltage": voltage, "Current": motor_i,
                   "Set RPM": rpm, "Read RPM": motor_s,
                   "Force": force, "Thrust": None}
            data = data.append(row, ignore_index=True)            

            time.sleep(0.05)

        # Stop thruster
        print("Stopping...")
        pkt = t.generatePacketFromRPM(0, dir='f', openloop=run_open_loop)
        ts.write(pkt)

        thrust = calc_median(_forces) * Coercive.MOMENT
        thrusts.append(thrust)
        read_rpm = calc_median(_read_rpms[:-10])
        read_rpms.append(read_rpm)
        current = calc_median(_currents)
        currents.append(current)

        # Wait for water to settle
        if (rpm != rpms[-1]):
            stp_init = time.time()
            while (time.time() - stp_init < stp_time):
                e = time.time() - stp_init      # elapsed
                r = stp_time - e                # remaining
                print(f"\rWaiting for water to settle {(e/stp_time*100):3.1f}%, ETA {r//60:2f}:{r%60:2f}", end="")
                time.sleep(1)

    print("\nDone! Saving and Plotting...")
    data.to_csv(f"tests/test_{time_str}.csv", na_rep="0")
    generate_plot(currents, read_rpms, thrusts, time_str)

def generate_plot(c, r, t, tm):
    if (len(c) != len(t) or len(r) != len(t)):
        print(f"Currents: {c}\nRPMs: {r}\nThrusts: {t}")
        raise Exception("Cannot generate plot. Array lengths do not match")
    else:
        p = [voltage*x for x in c]

        fig, ax = plt.subplots(layout="constrained")
        ax2 = ax.twinx()
        ax3 = ax.twinx()

        ax.set_xlabel("Thrust (kgf)")
        ax.set_ylabel("Power (W)")
        ax2.set_ylabel("Current (A)")
        ax3.set_ylabel("RPM read from thruster")

        c1, c2, c3 = plt.cm.viridis([0, .5, .9])

        ax.plot(t, p, color=c1, label="Power (W)")
        ax2.plot(t, c, color=c2, label="Current (A)")
        ax3.plot(t, r,color=c3, label="Read RPM")
        ax3.spines['right'].set_position(('outward', 40))

        plt.grid()
        # plt.suptitle(f"Currents: {c}\nRPMs: {r}\nThrusts: {t}")

        plt.savefig(f"tests/plot_{tm}.pdf", bbox_inches="tight")
        plt.show()

def calc_median(arr):
    std = pstdev(arr)
    avg = mean(arr)

    # eliminate measurements that are more than 2 standard deviations away from the mean
    arr = [f if (f < avg+(2*std) or f > avg-(2*std)) else 0 for f in arr]
    med = median(arr)
    return med

if __name__ == "__main__":
    try:
        # Initialize serial
        ts = serial.Serial('COM5', 57600)
        ms = serial.Serial('COM3', 9600)
        main(ts, ms)
    except KeyboardInterrupt:
        ts.close()
        ms.close()
        _exit(130)