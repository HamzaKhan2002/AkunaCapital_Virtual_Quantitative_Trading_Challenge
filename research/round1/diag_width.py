"""Lambda-book edge structure vs the Fixed Width 0.1 competitor."""
LAM = 0.88

print("lambda-book (lam=0.88, width 1-lam=0.12) vs Fixed Width 0.1 (0.05 per side)")
print(f"{'theo':>6}{'ourbid':>8}{'ouroff':>8}{'bidedge':>9}{'offedge':>9}  wins bid / wins offer")
for p in (0.05, 0.2, 0.5, 0.8, 0.9, 0.95):
    b, o = LAM * p, 1 - LAM * (1 - p)
    win_b = "US" if b > p - 0.05 else "FW"
    win_o = "US" if o < p + 0.05 else "FW"
    print(f"{p:>6.2f}{b:>8.3f}{o:>8.3f}{p - b:>9.3f}{o - p:>9.3f}  {win_b:>6} / {win_o:>6}")

print("\nwidth of the lambda-book is CONSTANT = 1-lam =", 1 - LAM)
print("but it is SPLIT asymmetrically: bid edge = p*(1-lam), offer edge = (1-p)*(1-lam)")
print("=> at p=0.9 we sell for 1.2c of edge and pay out 90% of the time.")
