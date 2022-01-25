import time
from statistics import mean
import hid


class WL100_Values:
    """
    A container for bucketed average values
    """

    MAX_DATA = 100_000
    OLDEST_DATA_SEC = 1800  # 30 min
    DECIMAL_PLACES = 2

    def __init__(self):
        self.values = []

        # buckets: instant (last read value), seconds, minutes
        self.instant = 0
        self.sec_1 = self.sec_5 = self.sec_15 = self.sec_30 = 0
        self.min_1 = self.min_5 = self.min_15 = self.min_30 = 0

    def add_value(self, value: float):
        """
        Adds a value and calculates the buckets

        :param value: new value to add to the data cache
        """

        # values are a tuple of the time they were stored and the dBA reading
        self.values.append((time.time(), value))
        self.prune()
        self.calculate()

    def prune(self):
        """Prunes old data out of the values cache"""
        if len(self.values) > self.MAX_DATA:
            self.values = self.values[self.MAX_DATA * -1 :]
        # this could be optimized
        self.values = self.get_values_in_last_seconds(self.OLDEST_DATA_SEC)

    def get_values_in_last_seconds(self, seconds: int) -> list:
        oldest = time.time() - seconds
        return [v for v in self.values if v[0] > oldest]

    def calculate(self):
        if not self.values:
            return None
        self.instant = self.values[-1][1]
        for group in ["sec", "min"]:
            for size in [1, 5, 15, 30]:
                if group == "min":
                    size_sec = size * 60
                else:
                    size_sec = size
                earliest = self.values[0][0]
                has_value = earliest <= (time.time() - size_sec)
                setattr(
                    self,
                    f"{group}_{size}",
                    round(
                        mean([v[1] for v in self.get_values_in_last_seconds(size_sec)]),
                        self.DECIMAL_PLACES,
                    )
                    if has_value
                    else None,
                )


class WL100:
    """
    Reads data from the WL100 USB-based Sound Pressure Level meter
    Identified by Vendor "Silicon Laboratories, Inc."
    or Manufacturer "SLAB"
    """

    # hardware programmers use hex!
    REPORT_ID = 0x05
    REPORT_MAX_LEN = 61

    REPORT_LEVEL_OFFSET = 0x07
    REPORT_LEVEL_LEN = 2

    def __init__(self, vendor_id: int = 0x10C4, product_id: int = 0x82CD):
        # In case you end up with the same chipset but a different product, get these from:
        #  linux: `lsusb`
        #  mac: `system_profiler SPUSBDataType` (look for WL100)
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = hid.device()
        self.wait_for_connection = 1  # sec

        self.values = WL100_Values()

    def open(self):
        """
        Opens the HID device
        """
        self.device.open(self.vendor_id, self.product_id)

    def get_report(self) -> list:
        """
        Fetches the report from the device
        :return list of byte values (ints)
        """
        return self.device.get_feature_report(self.REPORT_ID, self.REPORT_MAX_LEN)

    def parse_report(self, report: list) -> WL100_Values:
        level = report[
            self.REPORT_LEVEL_OFFSET : self.REPORT_LEVEL_OFFSET + self.REPORT_LEVEL_LEN
        ]
        # two bytes (534 == 53.4dBA):
        dB = ((level[0] << 8) + level[1]) / 10
        self.values.add_value(dB)
        return self.values

    def get_values(self, auto_reconnect: bool = True) -> WL100_Values:
        if not auto_reconnect:
            return self.parse_report(self.get_report())

        # try until we get a value
        # (in case the device was unplugged/otherwise disconnected)
        while True:
            try:
                return self.parse_report(self.get_report())
            except (OSError, ValueError):
                # device unplugged or similar
                try:
                    self.open()
                except OSError:
                    # try again in 1 sec
                    time.sleep(self.wait_for_connection)
                continue

    def get_value(self, auto_reconnect: bool = True) -> float:
        return self.get_values(auto_reconnect=auto_reconnect).instant


if __name__ == "__main__":
    import sys

    try:
        runtime = int(sys.argv[1])
    except (IndexError, ValueError):
        print("Running forever.", file=sys.stderr)
        runtime = None

    start = time.time()

    def show_value(wl100: WL100):
        v = wl100.get_values()
        print(f"{v.instant}dBA")
        print(f"(1sec={v.sec_1}, 5sec={v.sec_5}, 15sec={v.sec_15}, 30sec={v.sec_30})")
        print(f"(1min={v.min_1}, 5min={v.min_5}, 15min={v.min_15}, 30min={v.min_30})")
        print(f"{len(v.values)} values")
        print(f"Elapsed: {round(time.time()-start)}s")
        print()

    spl = WL100()
    until = time.time() + (runtime or 0)
    last = time.time()
    while runtime is None or until > time.time():
        spl.get_values()

        # every 1 second
        if time.time() > last + 1:
            show_value(spl)
            last = time.time()

        # collect 100 values/sec
        time.sleep(0.01)

    # one last time
    show_value(spl)
