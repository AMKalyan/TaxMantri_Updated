"""Indian number formatting: 1234567 -> '12,34,567'."""


def inr(value: float) -> str:
    n = int(round(value))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + s


def round_tax(value: float) -> float:
    """Section 288B: tax payable is rounded off to the nearest multiple of ₹10."""
    return float(int((value + 5) // 10 * 10))
