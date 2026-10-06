"""Specification-derived calibration oracles; never call source or target programs."""

from collections import deque
from fractions import Fraction
from functools import lru_cache
from itertools import product


def flipping_signs(values: list[int]) -> int:
    """Search every state reachable by an adjacent two-sign flip (small N only)."""
    if not 2 <= len(values) <= 8 or any(abs(x) > 10**9 for x in values):
        raise ValueError("Outside the bounded exhaustive-search domain")
    queue, seen = deque([0]), {0}
    best = sum(values)
    while queue:
        mask = queue.popleft()
        best = max(best, sum(-x if mask & (1 << i) else x for i, x in enumerate(values)))
        for i in range(len(values) - 1):
            neighbor = mask ^ (3 << i)
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return best


def digits(n: int, base: int) -> int:
    if not 1 <= n <= 10**9 or not 2 <= base <= 10:
        raise ValueError("Invalid digit-counting input")
    count = 0
    while n:
        n //= base
        count += 1
    return count


def vacation(jobs: list[tuple[int, int]], days: int) -> int:
    """Enumerate schedules, including idle days, rather than use a priority queue."""
    if not 1 <= len(jobs) <= 8 or not 1 <= days <= 6:
        raise ValueError("Outside the bounded schedule-search domain")
    if any(not 1 <= delay <= 10**5 or not 1 <= reward <= 10**4 for delay, reward in jobs):
        raise ValueError("Invalid job")

    @lru_cache(None)
    def search(day: int, used: int) -> int:
        if day == days:
            return 0
        best = search(day + 1, used)
        for i, (delay, reward) in enumerate(jobs):
            if not used & (1 << i) and day + delay <= days:
                best = max(best, reward + search(day + 1, used | (1 << i)))
        return best

    return search(0, 0)


def interest(goal: int) -> int:
    if not 101 <= goal <= 10**18:
        raise ValueError("Invalid deposit goal")
    balances = [100]
    while balances[-1] < goal:
        # Exact rational compounding followed by floor, from the stated bank rule.
        balances.append(int(Fraction(balances[-1]) * Fraction(101, 100)))
    return len(balances) - 1


def requirements(n: int, m: int, rules: list[tuple[int, int, int, int]]) -> int:
    """Enumerate the Cartesian input space and then filter nondecreasing sequences."""
    if not 2 <= n <= 5 or not 1 <= m <= 5 or not 1 <= len(rules) <= 50:
        raise ValueError("Outside the bounded requirements-search domain")
    if len({(a, b, c) for a, b, c, _ in rules}) != len(rules):
        raise ValueError("Duplicate requirement triple")
    if any(not (1 <= a < b <= n and 0 <= c < m and 1 <= d <= 10**5) for a, b, c, d in rules):
        raise ValueError("Invalid requirement")
    best = 0
    for sequence in product(range(1, m + 1), repeat=n):
        if any(x > y for x, y in zip(sequence, sequence[1:], strict=False)):
            continue
        score = sum(d for a, b, c, d in rules if sequence[b - 1] - sequence[a - 1] == c)
        best = max(best, score)
    return best


def answer(pair: str, input_text: str) -> str:
    tokens = input_text.split()
    if pair == "62549":
        n = int(tokens[0])
        strings = input_text.splitlines()[1:]
        if not 1 <= n <= 2 * 10**5 or len(strings) != n:
            raise ValueError("Invalid string count")
        if any(not 1 <= len(s) <= 10 or not all("a" <= x <= "z" for x in s) for s in strings):
            raise ValueError("Invalid prize string")
        distinct = []
        for s in strings:
            if s not in distinct:
                distinct.append(s)
        return f"{len(distinct)}\n"
    nums = list(map(int, tokens))
    if pair == "58801":
        if len(nums) != nums[0] + 1:
            raise ValueError("Invalid sequence length")
        value = flipping_signs(nums[1:])
    elif pair == "58902":
        if len(nums) != 2:
            raise ValueError("Require N and K")
        value = digits(*nums)
    elif pair == "59448":
        if len(nums) != 1 or not 1 <= nums[0] <= 100:
            raise ValueError("Invalid circle radius")
        value = pow(nums[0], 2)
    elif pair == "60194":
        n, days = nums[:2]
        if len(nums) != 2 + 2 * n:
            raise ValueError("Invalid job count")
        value = vacation(list(zip(nums[2::2], nums[3::2], strict=True)), days)
    elif pair == "60265":
        if len(nums) != 1:
            raise ValueError("Require one goal")
        value = interest(nums[0])
    elif pair == "60797":
        n, m, q = nums[:3]
        if len(nums) != 3 + 4 * q:
            raise ValueError("Invalid rule count")
        rules = [tuple(nums[i : i + 4]) for i in range(3, len(nums), 4)]
        value = requirements(n, m, rules)
    elif pair == "61358":
        if len(nums) != 1 or not 0 <= nums[0] <= 86400:
            raise ValueError("Invalid second count")
        hours, remainder = divmod(nums[0], 3600)
        minutes, seconds = divmod(remainder, 60)
        value = f"{hours}:{minutes}:{seconds}"
    elif pair == "61692":
        if len(nums) != 1 or not 1 <= nums[0] <= 999:
            raise ValueError("Invalid pencil count")
        value = ["pon", "pon", "hon", "bon", "hon", "hon", "pon", "hon", "pon", "hon"][nums[0] % 10]
    elif pair == "62222":
        if len(nums) != 1 or not 10 <= nums[0] <= 99:
            raise ValueError("Invalid two-digit integer")
        value = "Yes" if nums[0] // 10 == 9 or nums[0] % 10 == 9 else "No"
    else:
        raise ValueError("No reviewed calibration oracle for this pair")
    return f"{value}\n"
