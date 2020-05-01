import heapq


def get_median(data: list):
    """
    Calculates the median of the given list by using balanced min and max heaps.
    If there are no elements, this will return None.

    Parameters
    ----------
    data : list
        A list of numeric values.

    Returns
    -------
    float
        The median value as a float.
    None
        Only returned when the list is empty.

    """
    if len(data) == 0:
        return None

    # Max and min heaps.
    low = []
    high = []

    for num in data:
        # Add to the max heap.
        heapq.heappush(low, num)

        # Balance the two heaps.
        heapq.heappush(high, heapq.heappop(low) * -1)  # Invert to make it behave like a min heap.

        # Maintain heap size parity (well, almost parity) - the heaps can differ by at most 1 in size.
        if len(low) < len(high):
            heapq.heappush(low, heapq.heappop(high) * -1)  # Invert it again so it's back to its actual value.

    return heapq.heappop(low) if len(low) > len(high) else (heapq.heappop(low) + (heapq.heappop(high) * -1)) * 0.5


def get_mean(data: list):
    """
    Calculates the mean of the given list.

    Parameters
    ----------
    data : list
        A list of numeric values.

    Returns
    -------
    float
        The mean value as a float.
    None
        Only returned when the list is empty.

    """
    return sum(data) / len(data) if len(data) > 0 else None
