

def modular_inverse(a, n):
    """
    Extended Euclidean Algorithm. It's the 'division' in elliptic curves
    :param a: Divisor
    :param n: Mod for division
    :return: Value which fulfill equation `(value * a) % n == 1`
    """
    a = a % n
    if a == 0:
        return 0
    lm, hm = 1, 0
    low, high = a % n, n
    while low > 1:
        r = high // low
        nm, new = hm - lm * r, high - low * r
        lm, low, hm, high = nm, new, lm, low
    return lm % n


def legendre_symbol(a, p):
    """
    Computes the Legendre symbol
    :param a: number
    :param p: prime number
    :return: Returns 1 if `a` has a square root modulo p, -1 otherwise.
    """

    ls = pow(a, (p - 1) // 2, p)
    if ls == p - 1:
        return -1
    return ls


def modular_sqrt(a, p):
    """
    Tonelli-Shanks algorithm finding quadratic residue of `a` modulo `p`.
    :param a: number
    :param p: prime number
    :return: Value which fulfill equation `(value * value) % p == a` or
    0 when no square root exists.
    """

    # Simple cases handling
    if legendre_symbol(a, p) != 1:
        return 0
    elif a == 0:
        return 0
    elif p == 2:
        return p
    elif p % 4 == 3:
        return pow(a, (p + 1) // 4, p)
    s = p - 1
    e = 0
    while s % 2 == 0:
        s //= 2
        e += 1

    n = 2
    while legendre_symbol(n, p) != -1:
        n += 1
    x = pow(a, (s + 1) // 2, p)
    b = pow(a, s, p)
    g = pow(n, s, p)
    r = e
    while True:
        t = b
        m = 0
        for m in range(r):
            if t == 1:
                break
            t = pow(t, 2, p)
        if m == 0:
            return x
        gs = pow(g, 2 ** (r - m - 1), p)
        g = (gs * gs) % p
        x = (x * gs) % p
        b = (b * g) % p
        r = m
