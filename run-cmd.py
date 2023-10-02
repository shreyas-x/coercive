from coercive import Coercive
import serial
from os import _exit
import time

# thruster is at 57.6kbps
def initSerial():
    ser = serial.Serial('/dev/ttyUSB0', 57600)
    return ser

def closeSerial(ser):
    ser.close()

def serialDataReceivedCallback(data):
    Coercive.parseReply(data)
    # print(data)

def sendMessageOverSerial(ser, msg):
    ser.write(msg)

def main():
    ser = None

    thruster_id = 1
    thruster = Coercive(thruster_id)

    print("Init serial?: ", end="")
    init_serial = True if input() != "" else False

    if init_serial:
        ser = initSerial()


    while(1):
        readBuffer = []
        print("-----\nInput RPM between 0 and 2200: ", end="")
        if init_serial:
            try:
                inputRPM = input()
                print(f"Running thruster at {inputRPM} RPM")
                start = time.time()
                while(time.time() - start < 10):
                    sendMessageOverSerial(ser, thruster.generatePacketFromRPM(inputRPM, dir='f', openloop=True))
                    time.sleep(0.5)
                    for _ in range(20):
                        readBuffer.append(ser.read())
                    print(Coercive.parseReply(readBuffer, condensed=True))
                    readBuffer = []

                sendMessageOverSerial(ser, thruster.generatePacketFromRPM(0))
                print("Thruster stopped")
                ser.flush()

            except KeyboardInterrupt:
                closeSerial(ser)
                break

        else:
            print(thruster.generatePacketFromRPM(input()))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _exit(130)