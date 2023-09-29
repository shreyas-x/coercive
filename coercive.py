from math import floor

class Coercive:
    MOMENT = 0.464

    def __init__(self, id=1):
        if id <= 0:
            raise Exception("Thruster ID cannot be less than or equal to 0")
        elif id >= 8:
            raise Exception("Thruster ID cannot be greater than or equal to 8")
        else:
            self.thruster_id = id

    def checksum(self, data: list):
        # Checksum is sum of bytes 0-42 and 0xA5 (165 in decimal)
        return (sum(list(map(lambda x: int.from_bytes(x, byteorder="big"), data)), 165) & 0xFF).to_bytes(1, "big")
    
    def __getDemandBytesFromRPM(self, rpm: int):
        """Generate demand bytes from RPM input

        Args:
            rpm (int): Input RPM

        Returns:
            Tuple: Demand bytes in the format (MSB, LSB)
        """

        msb = b""
        lsb = b""
        if rpm <= 0:
            # print("Stopping thruster")
            rpm = 0
        if rpm > 2200:
            # print("RPM capped at 2200")
            rpm = 2200
        
        demand = floor(rpm/2800 * 65536).to_bytes(2, "big")
        msb = demand[0].to_bytes(1, "big")
        lsb = demand[1].to_bytes(1, "big")
        return (msb, lsb)

    def generatePacketFromRPM(self, rpm: str, dir: str='f', openloop: bool=True):
        """Creates a 44-byte 'fast packet' to be sent to thruster

        Args:
            rpm (str): Input RPM
            dir (int): Thruster direction, 0 forward 1 reverse
            openloop (bool): Run in open loop mode if True, closed loop mode if False

        Returns:
            bytes: bytearray of 44 bytes
        """
        # Sanitize
        if type(rpm) != int:
            try:
                rpm = int(rpm)
            except ValueError:
                print("Please enter a valid number")
                return b""
        if not (dir == 'f' or dir == 'r'):
            print("Please enter valid direction, either 'f' or 'r'")
            return b""
        
        # outgoing packet is 44 bytes
        pkt = []

        # Byte 0 - Thruster address 1-16
        # This will make the thruster specified in the address
        # to report back status
        pkt.append(self.thruster_id.to_bytes(1, "big"))

        '''
        # TODO: MODIFY SO THAT BYTES ARE POPULATED BASED ON THRUSTER ID
        '''

        for i in range(16):
            if i == self.thruster_id - 1:
                # Thruster demand is 0-65536 corresponding to 0-100% in 0.04% steps
                # or 0-2800RPM
                (msb, lsb) = self.__getDemandBytesFromRPM(rpm)
                # Byte 1 - Thruster demand address 1 LS Byte
                pkt.append(lsb)
                # Byte 2 - Thruster demand address 1 MS Byte
                pkt.append(msb)
            else:
                # Remaining all bytes x00 for now
                pkt.append(b'\x00')
                pkt.append(b'\x00')

        # Bytes 33 and 34 contain Thruster Direction Bits
        # 0 for forward and 1 for reverse
        if dir == 'f':
            pkt.append(b'\x00')
        elif dir == 'r':
            pkt.append(b'\x01')    # for thruster 1-8

        pkt.append(b'\x00')     # for thruster 9-16
        
        # Bytes 35 and 36 contain Thruster Demand Mode Bits
        # 0 for open loop mode, 1 for closed loop mode (RPM input)
        if openloop == True:
            pkt.append(b'\x00')
        else:
            pkt.append(b'\x01')    # for thruster 1-8

        pkt.append(b'\x00')     # for thruster 9-16

        # Bytes 37 and 38 contain Thruster Enable Bits
        # 0 is disable and 1 is enable
        pkt.append(b'\x01')     # for thruster 1-8
        pkt.append(b'\x00')     # for thruster 9-16

        # Bytes 39-42 are labeled spare
        for _ in range(4):
            pkt.append(b'\x00')

        pkt.append(self.checksum(pkt))
        return b"".join(pkt)
    
    @staticmethod
    def parseReply(reply: list, condensed: bool=False):
        """Parse reply from thruster and output neatly

        Args:
            reply (list): Reply from thruster
            condensed (bool): If True returns a succint version of the stats

        Returns:
            str: Formatted output of thruster status
        """

        # print(reply)
        if len(reply) <= 19:
            print(reply)
            print("No data")
            return
        
        # Byte 18 is status flag
        status = int.from_bytes(reply[18], "big")

        # Byte 0 is padding + 5 bit thruster address 0b100xxxxx
        thruster_address = int.from_bytes(reply[0], "big") & 0x1F

        # Bytes 1 and 2 are LSB and MSB of speed
        print(reply[2], reply[1])
        speed = int.from_bytes(b"".join([reply[2], reply[1]]), "big")
        direction = "forward" if (status & 0x01 == 0) else "reverse"

        # Bytes 3 and 4 are LSB and MSB of current
        current = (int.from_bytes( (b"".join([reply[4], reply[3]])), "big" ) & 0x3FF) / 59

        # Bytes 5 and 6 are LSB and MSB of temperature
        temp = int.from_bytes( (b"".join([reply[6], reply[5]])), "big" ) & 0x3FF
        slope = 146.9/200
        intercept = -245.8415
        temp_act = slope*temp + intercept

        # Errors from status byte 18
        leak = "Yes" if (status & 0x10 == 1) else "No"
        speed_err = "Yes" if (status & 0x08 == 1) else "No"
        over_temp = "Yes" if (status & 0x04 == 1) else "No"
        over_curr = "Yes" if (status & 0x02 == 1) else "No"

        if condensed == False:
            print(f"Thruster Address: {thruster_address}")
            print(f"Thruster Speed: {speed}, in the {direction} direction")
            print(f"Motor Current: {current:.2f}")
            print(f"Motor Temperature: {temp_act:.2f}")
            print(f"Leak: {leak} | Speed error: {speed_err} | Over-temperature: {over_temp} | Over-current: {over_curr}")
        
        elif condensed == True:
            condensedReply = f"{thruster_address},{speed},{direction},{current:.2f},{temp_act:.2f},{leak},{speed_err},{over_temp},{over_curr}"
            return condensedReply